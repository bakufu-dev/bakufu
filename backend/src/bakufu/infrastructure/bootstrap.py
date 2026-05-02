"""Backend 起動シーケンサ（Confirmation E + G + J + K + L）。

``docs/features/persistence-foundation/detailed-design/bootstrap.md`` に
記述された 8 段階のコールドスタート振付（choreography）を担う。1 つの
クラスに集約することで以下の利点が得られる:

* :meth:`Bootstrap.run` 内で順序を上から下に読める（Confirmation G）。
* LIFO クリーンアップ契約を ``try/finally`` で 1 か所に束ねられる
  （Confirmation J — Schneier 中等 4）。
* SQLite が WAL/SHM ファイルを開く *前* に ``os.umask(0o077)`` を
  設定できる（Confirmation L — Schneier 中等 1）。
* Stage 6 末尾でハンドラ未登録の WARN を可視化できる
  （Confirmation K — Schneier 中等 3）。
* 各 Stage 失敗時の FATAL ログ + ``exit(1)`` フローを集約し、テレメトリ
  形状を均質化できる。

実際の FastAPI バインド（Stage 8）は ``listener_starter`` callable で注入
する。これにより本 PR は ``feature/http-api`` の HTTP 表面を取り込まずに
リリース可能となる。テストでは ``None`` を渡して Stage 8 をまるごと
スキップする。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.llm_provider_port import LLMProviderPort
from bakufu.application.services.template_library import TemplateLibrarySeeder
from bakufu.infrastructure.config import data_dir
from bakufu.infrastructure.exceptions import (
    BakufuConfigError,
    BakufuMigrationError,
)
from bakufu.infrastructure.persistence.sqlite import db_file_mode, pid_gc
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite import session as session_mod
from bakufu.infrastructure.persistence.sqlite.outbox import (
    dispatcher as dispatcher_mod,
)
from bakufu.infrastructure.persistence.sqlite.outbox import (
    handler_registry,
)
from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository import (
    SqliteDeliverableTemplateRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository import (
    SqliteRoleProfileRepository,
)
from bakufu.infrastructure.security import masking
from bakufu.infrastructure.storage import attachment_root

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Confirmation L: secure-by-default のファイルモード（POSIX のみ）。
SECURE_UMASK: int = 0o077

# 任意の Stage 8 callable 用の型エイリアス。
ListenerStarter = Callable[[], Awaitable[None]]


class Bootstrap:
    """8 段階の起動オーケストレータ。

    テストは ``listener_starter=None`` で構築し :meth:`run` を呼んで、
    HTTP バインドなしの全シーケンスを検証する。本番では FastAPI バインダ
    を注入する。
    """

    def __init__(
        self,
        *,
        listener_starter: ListenerStarter | None = None,
        migration_runner: Callable[[AsyncEngine], Awaitable[str]] | None = None,
        event_bus: EventBusPort | None = None,
        llm_provider: LLMProviderPort | None = None,
    ) -> None:
        self._listener_starter = listener_starter
        # マイグレーションは Bootstrap から疎結合化されており、テストは
        # Alembic を起動せずスタブを差し込める。本番では
        # ``infrastructure.persistence.sqlite.migrations`` の Alembic 駆動
        # 実装を渡す。
        self._migration_runner = migration_runner

        # Stage 6.5 用: 外部から注入しない場合は Stage 6.5 で生成する。
        # テストは stub を差し込んで Stage 6.5 の起動を制御できる。
        self._event_bus: EventBusPort | None = event_bus
        self._llm_provider: LLMProviderPort | None = llm_provider

        # Stage が成功するごとに状態を埋めていく。失敗時は LIFO クリーン
        # アップが逆順に走査する。
        self._app_engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._dispatcher: dispatcher_mod.OutboxDispatcher | None = None
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._attachments_task: asyncio.Task[None] | None = None
        self._data_dir: Path | None = None
        # Stage 6.5: StageWorker 起動制御（§確定 C）
        self._stage_worker: object | None = None  # StageWorker（循環 import 回避のため object）
        self._stage_worker_task: asyncio.Task[None] | None = None

    @property
    def app_engine(self) -> AsyncEngine | None:
        """アプリケーション エンジン（Stage 2 成功までは ``None``）。"""
        return self._app_engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession] | None:
        """セッション ファクトリ（Stage 2 成功までは ``None``）。"""
        return self._session_factory

    async def run(self) -> None:
        """Stage 0〜8 を実行する。``finally`` ブロックが LIFO クリーンアップを行う。

        Raises:
            BakufuConfigError: いずれかの致命的 Stage（1/2/3/5/6/7/8）が
                失敗した場合。Stage 4（pid_gc）は WARN のみで非致命。
                ``AccessDenied`` 行は次回スイープに委ねる。
        """
        try:
            self._stage_0_umask()
            self._stage_1_resolve_data_dir()
            await self._stage_2_init_engine()
            await self._stage_3_migrate()
            await self._stage_3b_seed_template_library()
            await self._stage_4_pid_gc()
            self._stage_5_attachments()
            await self._stage_6_dispatcher()
            await self._stage_6_5_stage_worker()
            self._stage_7_orphan_scheduler()
            await self._stage_8_listener()
        finally:
            await self._cleanup()

    # ------------------------------------------------------------------
    # Stage 0: secure-by-default umask（Confirmation L）。
    # ------------------------------------------------------------------
    def _stage_0_umask(self) -> None:
        """SQLite が作成するファイルが ``0o600`` を継承するよう ``umask`` を設定する。

        POSIX のみ — Windows は ACL を使うため ``os.umask`` は no-op となる。
        より制限的な umask 設定の失敗自体は致命ではない。OS デフォルトは
        ``0o022`` のままだが、Stage 5 / Alembic で明示的な ``chmod`` を
        実施しているため補正される。
        """
        if platform.system() == "Windows":
            return
        try:
            os.umask(SECURE_UMASK)
            logger.info(
                "[INFO] Bootstrap stage 0/8: umask set to 0o%03o",
                SECURE_UMASK,
            )
        except OSError as exc:  # pragma: no cover — extreme OS state
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=f"[FAIL] Bootstrap stage 0/8: umask SET failed: {exc!r}",
            ) from exc

    # ------------------------------------------------------------------
    # Stage 1: BAKUFU_DATA_DIR の解決。
    # ------------------------------------------------------------------
    def _stage_1_resolve_data_dir(self) -> None:
        logger.info("[INFO] Bootstrap stage 1/8: resolving BAKUFU_DATA_DIR...")
        try:
            self._data_dir = data_dir.resolve()
        except BakufuConfigError as exc:
            logger.error("[FAIL] Bootstrap stage 1/8: %s", exc.message)
            raise
        # 後続 Stage が競合なく書き込めるよう、ディレクトリ自体をここで
        # 実体化する。``exist_ok=True`` により再起動時も安価に冪等動作する。
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BakufuConfigError(
                msg_id="MSG-PF-001",
                message=(
                    f"[FAIL] Bootstrap stage 1/8: cannot create data_dir at "
                    f"{self._data_dir}: {exc!r}"
                ),
            ) from exc
        logger.info(
            "[INFO] Bootstrap stage 1/8: data dir resolved at %s",
            self._data_dir,
        )

    # ------------------------------------------------------------------
    # Stage 2: SQLite エンジン + マスキング ゲートウェイ初期化。
    # ------------------------------------------------------------------
    async def _stage_2_init_engine(self) -> None:
        logger.info("[INFO] Bootstrap stage 2/8: initializing SQLite engine...")
        if self._data_dir is None:  # pragma: no cover — stage ordering
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=(
                    "[FAIL] Bootstrap stage 2/8: data_dir not resolved (stage 1 must run first)"
                ),
            )
        # マスキング ゲートウェイをエンジンより *前* に初期化する。テーブル
        # 群は import 時にリスナを登録し、リスナは即座に ``mask`` を呼ぶ
        # ためである。
        try:
            masking.init()
        except BakufuConfigError:
            # MSG-PF-008 のケースはそのまま再送出する。マスキング初期化
            # 失敗時の Bootstrap 終了は Fail-Fast 契約である。
            raise
        url = f"sqlite+aiosqlite:///{self._data_dir / 'bakufu.db'}"
        try:
            self._app_engine = engine_mod.create_engine(url)
            self._session_factory = session_mod.make_session_factory(self._app_engine)
        except Exception as exc:
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=(
                    f"[FAIL] Bootstrap stage 2/8: SQLite engine initialization failed: {exc!r}"
                ),
            ) from exc
        logger.info(
            "[INFO] Bootstrap stage 2/8: engine ready (PRAGMA WAL/foreign_keys/"
            "busy_timeout/synchronous/temp_store/defensive applied)"
        )

    # ------------------------------------------------------------------
    # Stage 3: マイグレーション エンジン経由の Alembic upgrade（Confirmation D-3）。
    # ------------------------------------------------------------------
    async def _stage_3_migrate(self) -> None:
        logger.info("[INFO] Bootstrap stage 3/8: applying Alembic migrations...")
        if self._app_engine is None:  # pragma: no cover — stage ordering
            raise BakufuMigrationError(
                msg_id="MSG-PF-004",
                message="[FAIL] Bootstrap stage 3/8: app_engine not initialized",
            )
        if self._migration_runner is None:
            # テストや最小起動構成では runner が渡されない。本番配線の
            # 失敗を可視化するため WARN を出してスキップする。
            logger.warning(
                "[WARN] Bootstrap stage 3/8: no migration_runner injected; "
                "skipping Alembic upgrade (test-mode or minimal startup)."
            )
            return
        try:
            head = await self._migration_runner(self._app_engine)
        except Exception as exc:
            raise BakufuMigrationError(
                msg_id="MSG-PF-004",
                message=f"[FAIL] Alembic migration failed: {exc!r}",
            ) from exc
        logger.info("[INFO] Bootstrap stage 3/8: schema at head %s", head)

        # REQ-PF-002-A（Schneier 致命1）: Stage 0 で ``umask 0o077`` を
        # 設定し新規作成ファイルが ``0o600`` を継承するようにしているが、
        # umask を設定せずに起動した *過去の* bakufu 実行が、これらの
        # ファイルを ``0o644`` のまま残している可能性がある。data_dir が
        # 解決済みで DB ファイルが確実に存在する（Alembic が直前に書き
        # 込んでいる）ここで監査と修復を実施する。chmod 失敗時は ERROR
        # ログのみで継続する（非致命）。起動を拒否するとリカバリ経路を
        # 塞いでしまうためである。
        if self._data_dir is not None:
            mode_results = db_file_mode.verify_and_repair(self._data_dir)
            logger.info(
                "[INFO] Bootstrap stage 3/8: DB file mode audit: %s",
                mode_results,
            )

    # ------------------------------------------------------------------
    # Stage 3b: template-library seed（Alembic 直後、PID GC 直前）。
    # ------------------------------------------------------------------
    async def _stage_3b_seed_template_library(self) -> None:
        """WELL_KNOWN_TEMPLATES 12 件を UPSERT し、起動時に DB と定数を同期する。

        Stage 3（Alembic migration）完了後に実行することで、スキーマ確定前の
        write を防ぐ（REQ-TL-002）。session_factory が None の場合（Stage 2 未完）
        はガードして返す。
        """
        if self._session_factory is None:  # pragma: no cover — stage ordering
            return
        from bakufu.application.services.template_library.definitions import (
            WELL_KNOWN_TEMPLATES,
        )

        n = len(WELL_KNOWN_TEMPLATES)
        logger.info(
            "[INFO] Bootstrap stage 3b/8: seeding template-library (%d templates)...",
            n,
        )
        seeder = TemplateLibrarySeeder(
            template_repo_factory=SqliteDeliverableTemplateRepository,
            role_profile_repo_factory=SqliteRoleProfileRepository,
        )
        try:
            upserted = await seeder._seed_global_templates(self._session_factory)
        except Exception as exc:
            logger.error(
                "[FAIL] Bootstrap stage 3b/8: template-library seed failed: %s: %s",
                exc.__class__.__name__,
                exc,
            )
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=(
                    f"[FAIL] Bootstrap stage 3b/8: template-library seed failed:"
                    f" {exc.__class__.__name__}: {exc}"
                ),
            ) from exc
        logger.info(
            "[INFO] Bootstrap stage 3b/8: template-library seed complete (upserted=%d)",
            upserted,
        )

    # ------------------------------------------------------------------
    # Stage 4: pid_registry オーファン GC（非致命）。
    # ------------------------------------------------------------------
    async def _stage_4_pid_gc(self) -> None:
        logger.info("[INFO] Bootstrap stage 4/8: pid_registry orphan GC...")
        if self._session_factory is None:  # pragma: no cover — stage ordering
            return
        try:
            counts = await pid_gc.run_startup_gc(self._session_factory)
            logger.info(
                "[INFO] Bootstrap stage 4/8: GC complete "
                "(killed=%d, protected=%d, absent=%d, access_denied=%d)",
                counts["killed"],
                counts["protected"],
                counts["absent"],
                counts["access_denied"],
            )
        except Exception as exc:
            # Confirmation E + G: Stage 4 は非致命。残った行は次回 GC で
            # 処理し、Backend は起動を継続する。
            logger.warning(
                "[WARN] Bootstrap stage 4/8: pid_registry GC raised (%r); continuing startup",
                exc,
            )

    # ------------------------------------------------------------------
    # Stage 5: 添付ファイル FS ルート（Confirmation E）。
    # ------------------------------------------------------------------
    def _stage_5_attachments(self) -> None:
        logger.info("[INFO] Bootstrap stage 5/8: ensuring attachment FS root...")
        if self._data_dir is None:  # pragma: no cover — stage ordering
            raise BakufuConfigError(
                msg_id="MSG-PF-003",
                message="[FAIL] Bootstrap stage 5/8: data_dir not resolved",
            )
        root = attachment_root.ensure_root(self._data_dir)
        logger.info(
            "[INFO] Bootstrap stage 5/8: attachments root at %s (mode=0o%03o)",
            root,
            attachment_root.ATTACHMENTS_MODE,
        )

    # ------------------------------------------------------------------
    # Stage 6: Outbox ディスパッチャ（Confirmation K Fail Loud）。
    # ------------------------------------------------------------------
    async def _stage_6_dispatcher(self) -> None:
        logger.info(
            "[INFO] Bootstrap stage 6/8: starting Outbox Dispatcher "
            "(poll_interval=%ss, batch=%d)...",
            dispatcher_mod.DEFAULT_POLL_INTERVAL_SECONDS,
            dispatcher_mod.DEFAULT_BATCH_SIZE,
        )
        if self._session_factory is None:  # pragma: no cover — stage ordering
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message="[FAIL] Bootstrap stage 6/8: session_factory not ready",
            )
        self._dispatcher = dispatcher_mod.OutboxDispatcher(self._session_factory)
        self._dispatcher_task = asyncio.create_task(self._dispatcher.run())
        size = handler_registry.size()
        logger.info(
            "[INFO] Bootstrap stage 6/8: dispatcher running (handler_registry size=%d)",
            size,
        )
        # Confirmation K 行 1: 起動時にレジストリが空の場合 WARN を出す。
        if size == 0:
            logger.warning(
                "[WARN] Bootstrap stage 6/8: No event handlers registered. "
                "Outbox events will accumulate without dispatch. Register "
                "handlers via feature/{event-kind}-handler PRs before "
                "processing real events."
            )

    # ------------------------------------------------------------------
    # Stage 6.5: StageWorker 起動（§確定 C）。
    # ------------------------------------------------------------------
    async def _stage_6_5_stage_worker(self) -> None:
        """StageWorker を asyncio.create_task でスケジュールし Stage 6.5 として登録する。

        起動ロジックは StageWorkerBootstrap に委譲する（SRP）。
        LLM プロバイダ未設定時は WARNING のみで StageWorker をスキップする。
        """
        if self._session_factory is None:  # pragma: no cover — stage ordering
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message="[FAIL] Bootstrap stage 6.5/8: session_factory not ready",
            )

        from bakufu.infrastructure.worker.stage_worker_bootstrap import StageWorkerBootstrap

        stage_worker_bootstrap = StageWorkerBootstrap(
            session_factory=self._session_factory,
            event_bus=self._event_bus,
            llm_provider=self._llm_provider,
        )
        await stage_worker_bootstrap.start()

        self._stage_worker = stage_worker_bootstrap.worker
        self._event_bus = stage_worker_bootstrap.event_bus
        self._llm_provider = stage_worker_bootstrap.llm_provider

    # ------------------------------------------------------------------
    # Stage 7: 添付ファイル オーファン GC スケジューラ。
    # ------------------------------------------------------------------
    def _stage_7_orphan_scheduler(self) -> None:
        logger.info(
            "[INFO] Bootstrap stage 7/8: starting attachment orphan GC scheduler (interval=24h)..."
        )
        self._attachments_task = attachment_root.start_orphan_gc_scheduler()
        logger.info("[INFO] Bootstrap stage 7/8: scheduler running")

    # ------------------------------------------------------------------
    # Stage 8: FastAPI / WebSocket バインド（委譲）。
    # ------------------------------------------------------------------
    async def _stage_8_listener(self) -> None:
        if self._listener_starter is None:
            logger.info(
                "[INFO] Bootstrap stage 8/8: no listener_starter injected; "
                "skipping HTTP bind (skeleton mode)."
            )
            return
        logger.info("[INFO] Bootstrap stage 8/8: binding FastAPI listener (delegated)...")
        try:
            await self._listener_starter()
        except Exception as exc:
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=f"[FAIL] Bootstrap stage 8/8: listener bind failed: {exc!r}",
            ) from exc
        logger.info("[INFO] Bootstrap stage 8/8: bakufu Backend ready")

    # ------------------------------------------------------------------
    # LIFO クリーンアップ（Confirmation J）。
    # ------------------------------------------------------------------
    async def _cleanup(self) -> None:
        """async タスクを起動と逆順でキャンセルし、最後にエンジンを破棄する。

        順序（Confirmation J より）:

        1. 添付ファイル オーファン GC スケジューラを cancel（Stage 7）。
        2. Outbox ディスパッチャを stop し、タスクを cancel（Stage 6）。
        3. アプリケーション エンジンを dispose（Stage 2）。
        4. ログハンドラを flush。
        """
        # Stage 7 のクリーンアップ — Stage 6 側のクリーンアップで起こり
        # 得る別の問題を 1 つの CancelledError でマスクしないよう、
        # ``return_exceptions=True`` 付きの ``gather`` を使う。
        if self._attachments_task is not None:
            self._attachments_task.cancel()
            await asyncio.gather(self._attachments_task, return_exceptions=True)

        # Stage 6.5 のクリーンアップ — LIFO 順（Stage 7 → Stage 6.5 → Stage 6）。
        if self._stage_worker is not None:
            with contextlib.suppress(Exception):
                from bakufu.infrastructure.worker.stage_worker import StageWorker

                if isinstance(self._stage_worker, StageWorker):
                    await self._stage_worker.stop()

        if self._dispatcher is not None:
            await self._dispatcher.stop()
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            await asyncio.gather(self._dispatcher_task, return_exceptions=True)

        if self._app_engine is not None:
            await self._app_engine.dispose()

        for handler in logger.handlers:
            with contextlib.suppress(Exception):  # pragma: no cover — defensive
                handler.flush()


__all__ = [
    "SECURE_UMASK",
    "Bootstrap",
    "ListenerStarter",
]
