# 詳細設計補章: マスキング契約

> 親: [`../detailed-design.md`](../detailed-design.md)。本書はマスキングゲートウェイの正規表現セット（確定 A）と Fail-Secure フォールバック契約（確定 F、Schneier 重大 1 対応）を凍結する。

## 確定 A: マスキング 9 種正規表現 + 環境変数 + ホームパス

[`storage.md`](../../../architecture/domain-model/storage.md) §マスキング対象パターン の表を本 feature の `masking.py` に**そのまま**実装する。改変・追加は本 Issue では行わない（追加が必要な場合は別 Issue で `storage.md` 更新 + 同期 PR）。

### 9 種の正規表現（凍結）

| 種別 | 正規表現 | 置換後 |
|----|----|----|
| Anthropic API key | `sk-ant-(api03-)?[A-Za-z0-9_\-]{40,}` | `<REDACTED:ANTHROPIC_KEY>` |
| OpenAI API key | `sk-[A-Za-z0-9]{20,}`（`sk-ant-` を除く、negative lookahead） | `<REDACTED:OPENAI_KEY>` |
| GitHub PAT | `(ghp\|gho\|ghu\|ghs\|ghr)_[A-Za-z0-9]{36,}` | `<REDACTED:GITHUB_PAT>` |
| GitHub fine-grained PAT | `github_pat_[A-Za-z0-9_]{82,}` | `<REDACTED:GITHUB_PAT>` |
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `<REDACTED:AWS_ACCESS_KEY>` |
| AWS Secret | `aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}` | `<REDACTED:AWS_SECRET>` |
| Slack token | `xox[baprs]-[A-Za-z0-9-]{10,}` | `<REDACTED:SLACK_TOKEN>` |
| Discord bot token | `[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}` | `<REDACTED:DISCORD_TOKEN>` |
| Bearer / Authorization | `(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]+` | `\1<REDACTED:BEARER>` |

### 適用順序（厳守）

1. 環境変数値（最も具体的、長さ 8 以上のみ）
2. 正規表現 9 種（リスト順は OpenAI が `sk-ant-` を除く必要があるため Anthropic を先に適用）
3. ホームパス（`$HOME` 絶対パス → `<HOME>`）

## 確定 F: マスキング適用の **Fail-Secure** 契約（Schneier 重大 1 対応）

`MaskingGateway.mask()` / `mask_in()` は**例外を投げない契約**だが、内部の異常時には **生データを書く経路をゼロにする** Fail-Secure フォールバックを採用する。「永続化を止めない」より「秘密を漏らさない」を優先順位の上位に置く。Fail Securely 原則（[OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)）に従う。

### Fail-Secure フォールバック表（凍結）

| 状況 | フォールバック | 結果として永続化される値 |
|----|----|----|
| `mask_in` が想定外の型（datetime, bytes 等）に出会う | `str()` で文字列化してから `mask()` 適用 | masking 適用後の文字列 |
| `mask` が文字列処理中に予期せぬ例外を raise | catch して **入力 str 全体を `<REDACTED:MASK_ERROR>` に完全置換** + WARN ログ | `<REDACTED:MASK_ERROR>`（生データは絶対に書かない） |
| 正規表現マッチ中の例外（理論上発生しない） | 同上 | `<REDACTED:MASK_ERROR>` |
| `mask_in` が再帰中に容量制限超過（10MB 等の異常 dict） | 当該 dict / list 全体を `<REDACTED:MASK_OVERFLOW>` に置換 + WARN ログ | `<REDACTED:MASK_OVERFLOW>` |
| listener 自体が予期せぬ例外を raise | listener の outer catch で row のすべての masking 対象フィールドを `<REDACTED:LISTENER_ERROR>` に置換 + ERROR ログ + 永続化は続行 | 全 masking 対象フィールドが `<REDACTED:*>` になる |

### 環境変数辞書ロードは **Fail Fast**（Schneier 重大 1 (B) 対応）

masking の最初の layer（環境変数値の伏字化）が無効化された状態での起動は許容しない。

| 状況 | 挙動 |
|----|----|
| 起動時に `os.environ` から既知 env キー（ANTHROPIC_API_KEY 等）の取得自体が失敗 | OS 例外発生時のみ。`BakufuConfigError(MSG-PF-008)` を raise → プロセス終了 |
| 既知 env キーが**全て未設定**（CI 環境等） | OK。空のパターン辞書で起動（`MaskedEnvPatterns` のサイズ 0 ログ INFO 出力） |
| 既知 env キーの値が長さ 7 以下（短すぎて誤マッチを起こす） | スキップ（パターン辞書に追加しない、INFO ログ）|
| パターン辞書の compile に失敗（理論上発生しない） | `BakufuConfigError(MSG-PF-008)` raise → プロセス終了 |

「空辞書として継続、WARN ログ」を**削除**する。masking layer 1 が有効でない状態での bakufu 起動は信頼境界の前提を崩す。

### listener の永続化を「止めない」契約は維持、ただし「生データを書かない」を絶対不変条件として上位化

旧契約: 「Outbox 全体が止まると bakufu 全体が機能停止」を理由に listener の masking スキップを許容していた。

新契約: **listener は常に何らかの masking 後値を書く**（`<REDACTED:MASK_ERROR>` / `<REDACTED:LISTENER_ERROR>` / `<REDACTED:MASK_OVERFLOW>` のいずれかでも、生データは絶対に書かない）。

論拠:
- bakufu は CEO 個人の秘密が永続化される環境であり、business continuity > security の優先順位は逆
- 「listener が masking スキップ → 生データが書かれる」経路は、攻撃者が ENV ロード失敗 / 型異常を誘発する単一経路で全マスキングを無効化できる単一障害点
- 永続化を「止めない」のではなく「`<REDACTED:*>` で書く」ことで運用継続性も維持される（dead-letter 化経路は masking 後値で動作する）

### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-UT-PF-006-A | mask が予期せぬ例外 raise 時に `<REDACTED:MASK_ERROR>` が返る |
| TC-UT-PF-006-B | mask_in が異常 dict（10MB 超）受信時に `<REDACTED:MASK_OVERFLOW>` が返る |
| TC-UT-PF-006-C | listener 自体が例外時、row の全 masking 対象フィールドが `<REDACTED:LISTENER_ERROR>` になる |
| TC-IT-PF-007-D | 環境変数辞書ロード失敗時に Bootstrap が exit 1 する（Fail Fast） |
