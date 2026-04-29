""":class:`bakufu.application.ports.AgentRepository` の SQLite アダプタ。

§確定 B の "delete-then-insert" 保存フローを 3 つのテーブル
（``agents`` / ``agent_providers`` / ``agent_skills``）に対して実装する:

1. ``agents`` UPSERT（id 衝突時に name + role + persona + archived を更新。
   ``prompt_body`` は :class:`MaskedText` 経由でバインドされるため、埋め込まれた
   API キー / OAuth トークン / GitHub PAT は SQLite に到達する *前* に伏字化される —
   Schneier 申し送り #3 を Agent 経路にも適用）。
2. ``agent_providers`` DELETE WHERE agent_id = ?
3. ``agent_providers`` 一括 INSERT（ProviderConfig ごとに 1 行）。
4. ``agent_skills`` DELETE WHERE agent_id = ?
5. ``agent_skills`` 一括 INSERT（SkillRef ごとに 1 行）。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで上記 5 ステップ
を 1 トランザクションに収める（§確定 B Tx 境界の責務分離）。

``_to_row`` / ``_from_row`` はクラスのプライベートメソッドのまま保持し、双方向の
変換が隣接して存在するようにする。これにより、テストが公開された変換 API を誤って
取得して依存することを避ける（§確定 C）。

empire / workflow リポジトリ テンプレートを Agent 固有に拡張する 2 つのコントラクト:

* **§確定 F — :meth:`find_by_name`**: ``WHERE empire_id = :empire_id AND name =
  :name LIMIT 1`` でルックアップをスコープする追加の Protocol メソッド。実装は意図的に
  AgentId が判明し次第 :meth:`find_by_id` に委譲する — ``_from_row`` の変換ロジックを
  単一情報源に保つため。
* **§確定 H — 伏字化された ``prompt_body`` は不可逆**: :meth:`find_by_id` 経由の水和は、
  ``prompt_body`` が伏字化された形（例 ``<REDACTED:ANTHROPIC_KEY>``）の Persona を返す。
  伏字化されたプロンプトのディスパッチ拒否はアプリケーション層の責務であり、
  ``feature/llm-adapter`` のフォローアップとして凍結されている。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.agent import Agent, Persona, ProviderConfig, SkillRef
from bakufu.domain.value_objects import (
    AgentId,
    EmpireId,
    ProviderKind,
    Role,
)
from bakufu.infrastructure.persistence.sqlite.tables.agent_providers import (
    AgentProviderRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.agent_skills import (
    AgentSkillRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.agents import AgentRow


class SqliteAgentRepository:
    """:class:`AgentRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, agent_id: AgentId) -> Agent | None:
        """agent と関連テーブルを SELECT し、:meth:`_from_row` で水和する。

        agents 行が存在しない場合は ``None`` を返す。関連テーブルの SELECT は
        ``ORDER BY provider_kind`` / ``ORDER BY skill_id`` を使い、水和されたリスト
        が決定的になるようにする — empire-repository BUG-EMR-001 が凍結したコントラクト
        を本 PR の最初から適用する。
        """
        agent_stmt = select(AgentRow).where(AgentRow.id == agent_id)
        agent_row = (await self._session.execute(agent_stmt)).scalar_one_or_none()
        if agent_row is None:
            return None

        # ORDER BY を付与することで find_by_id を決定的にする。これがないと SQLite は
        # 内部スキャン順で行を返し、``Agent == Agent`` の往復等価性が壊れる
        # （Aggregate はリスト同士で比較する）。basic-design および workflow-repo
        # §BUG-EMR-001 を参照 — 本 PR では当初から決定の済んだコントラクトを採用する。
        provider_stmt = (
            select(AgentProviderRow)
            .where(AgentProviderRow.agent_id == agent_id)
            .order_by(AgentProviderRow.provider_kind)
        )
        provider_rows = list((await self._session.execute(provider_stmt)).scalars().all())

        skill_stmt = (
            select(AgentSkillRow)
            .where(AgentSkillRow.agent_id == agent_id)
            .order_by(AgentSkillRow.skill_id)
        )
        skill_rows = list((await self._session.execute(skill_stmt)).scalars().all())

        return self._from_row(agent_row, provider_rows, skill_rows)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM agents``。

        実装詳細: SQLAlchemy の ``func.count()`` は適切な ``SELECT COUNT(*)`` を
        発行するため、SQLite は全 PK を Python にストリームせずスカラー 1 行だけ返す。
        これは empire-repository §確定 D 補強コントラクトの継続である — Agent の
        provider / skill 行はプリセット ライブラリが入ると数百件を保持し得るため、
        このパターンが効いてくる。
        """
        stmt = select(func.count()).select_from(AgentRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, agent: Agent) -> None:
        """§確定 B の 5 ステップ delete-then-insert で ``agent`` を永続化する。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。各ステップ
        内部の失敗はそのまま伝播するため、アプリケーション サービスの Unit-of-Work
        境界はクリーンにロールバックできる。
        """
        agent_row, provider_rows, skill_rows = self._to_row(agent)

        # Step 1: agents UPSERT（id PK、ON CONFLICT で name + role + Persona フィールド
        # + archived を更新）。``prompt_body`` は MaskedText 経由でバインドされるため、
        # 更新時にも伏字化された形で DB に到達する。
        upsert_stmt = sqlite_insert(AgentRow).values(agent_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "empire_id": upsert_stmt.excluded.empire_id,
                "name": upsert_stmt.excluded.name,
                "role": upsert_stmt.excluded.role,
                "display_name": upsert_stmt.excluded.display_name,
                "archetype": upsert_stmt.excluded.archetype,
                "prompt_body": upsert_stmt.excluded.prompt_body,
                "archived": upsert_stmt.excluded.archived,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 2: agent_providers DELETE。
        await self._session.execute(
            delete(AgentProviderRow).where(AgentProviderRow.agent_id == agent.id)
        )

        # Step 3: agent_providers 一括 INSERT（providers が無い場合はスキップ —
        # Agent 不変条件は最低 1 つの provider を要求するが、空チェックは empire /
        # workflow テンプレートとの動作整合のために残す）。
        if provider_rows:
            await self._session.execute(insert(AgentProviderRow), provider_rows)

        # Step 4: agent_skills DELETE。
        await self._session.execute(delete(AgentSkillRow).where(AgentSkillRow.agent_id == agent.id))

        # Step 5: agent_skills 一括 INSERT（skill 集合は正当に空となり得る —
        # Agent はゼロ skill を許容する）。
        if skill_rows:
            await self._session.execute(insert(AgentSkillRow), skill_rows)

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Agent | None:
        """``empire_id`` 内の ``name`` という Agent を水和する（§確定 F）。

        2 段階フロー: 軽量な ``SELECT id ... LIMIT 1`` で AgentId を特定し、その後
        :meth:`find_by_id` に委譲することで関連テーブルの SELECT と ``_from_row``
        変換を単一情報源に保つ（§設計判断補足「find_by_id 経由で復元する根拠」）。
        """
        id_stmt = (
            select(AgentRow.id)
            .where(AgentRow.empire_id == empire_id, AgentRow.name == name)
            .limit(1)
        )
        found_id = (await self._session.execute(id_stmt)).scalar_one_or_none()
        if found_id is None:
            return None
        return await self.find_by_id(found_id)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(
        self,
        agent: Agent,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """``agent`` を ``(agent_row, provider_rows, skill_rows)`` に分割する。

        ここでは SQLAlchemy の ``Row`` オブジェクトを意図的に使わない。これによって
        ドメイン層が SQLAlchemy の型階層に偶発的に依存することを防ぐ。返却される
        各 ``dict`` のキーは対応するテーブルの ``mapped_column`` 名と完全一致する。
        """
        agent_row: dict[str, Any] = {
            "id": agent.id,
            "empire_id": agent.empire_id,
            "name": agent.name,
            "role": agent.role.value,
            "display_name": agent.persona.display_name,
            "archetype": agent.persona.archetype,
            # MaskedText.process_bind_param は json.dumps / VARCHAR ストレージに
            # 到達する前にこの文字列からシークレットを伏字化する —
            # Schneier 申し送り #3。
            "prompt_body": agent.persona.prompt_body,
            "archived": agent.archived,
        }
        provider_rows: list[dict[str, Any]] = [
            {
                "agent_id": agent.id,
                "provider_kind": provider.provider_kind.value,
                "model": provider.model,
                "is_default": provider.is_default,
            }
            for provider in agent.providers
        ]
        skill_rows: list[dict[str, Any]] = [
            {
                "agent_id": agent.id,
                "skill_id": skill.skill_id,
                "name": skill.name,
                "path": skill.path,
            }
            for skill in agent.skills
        ]
        return agent_row, provider_rows, skill_rows

    def _from_row(
        self,
        agent_row: AgentRow,
        provider_rows: list[AgentProviderRow],
        skill_rows: list[AgentSkillRow],
    ) -> Agent:
        """3 つの行から :class:`Agent` Aggregate Root を水和する。

        ``Agent.model_validate`` は post-validator を再実行するため、リポジトリ側
        の水和も ``AgentService.hire()`` が構築時に走らせるのと同じ不変条件チェック
        を通る。コントラクト（§確定 C）は「リポジトリ水和は妥当な Agent を生成するか
        例外を送出する」。

        §確定 H §不可逆性: ``persona.prompt_body`` はディスクから既に伏字化された
        テキストを保持する。``Persona`` は長さ上限内の任意の文字列を受理するため
        伏字化された形でも構築は通るが、生成された Agent は ``feature/llm-adapter``
        の masked-prompt ガード無しに LLM へディスパッチすべきではない。
        """
        persona = Persona(
            display_name=agent_row.display_name,
            archetype=agent_row.archetype,
            prompt_body=agent_row.prompt_body,
        )
        providers = [
            ProviderConfig(
                provider_kind=ProviderKind(row.provider_kind),
                model=row.model,
                is_default=row.is_default,
            )
            for row in provider_rows
        ]
        skills = [
            SkillRef(
                skill_id=row.skill_id,
                name=row.name,
                path=row.path,
            )
            for row in skill_rows
        ]
        return Agent(
            id=agent_row.id,
            empire_id=agent_row.empire_id,
            name=agent_row.name,
            role=Role(agent_row.role),
            persona=persona,
            providers=providers,
            skills=skills,
            archived=agent_row.archived,
        )


__all__ = ["SqliteAgentRepository"]
