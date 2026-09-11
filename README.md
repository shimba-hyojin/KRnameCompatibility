[한국어](README.ko.md) | **日本語**

# 韓国式 名前相性診断 (name-compat)

韓国で定番の遊び「이름궁합（名前の画数占い）」を、日本の同僚が説明なしで楽しめるようにした小さな Web サービスです。
自分の名前は **심효진（シム・ヒョジン）** に固定されており、利用者は相手の名前だけをハングルで入力します。

実際の目的は AWS と Observability の学習です。Linux・EC2・Nginx・Docker・Flask・MySQL(RDS)・
外部 API 連携・HTTPS・セキュリティグループ・ロギング・モニタリング・Datadog を、
ひとつのサービスの中でまとめて扱います。

**現在のデプロイ状況**: EC2 (`hyojin-ubuntu`) + RDS (`hyojin-db`, 東京リージョン)。
社内セキュリティポリシー上 80 番ポートを外部公開できないため、SSH トンネル経由でアクセスします
→ [`DEPLOY.md`](DEPLOY.md) 1-3 節。

---

## すぐ試す

依存パッケージなしで UI だけ確認する:

```bash
open preview.html          # macOS
```

依存パッケージなしで API まで確認する（標準ライブラリのみ使用）:

```bash
cd backend && python3 devserver.py     # http://localhost:8080
```

Docker でフルスタック（MySQL 込み）:

```bash
cp .env.example .env
docker compose --profile local up -d --build
open http://localhost
```

EC2 にデプロイしたものを見る（SSH トンネル）:

```bash
ssh -i ~/.ssh/hyojin-key.pem -L 8888:localhost:80 ubuntu@<EC2_IP>
# トンネルを開いたまま http://localhost:8888
```

GitHub Pages 版（サーバー不要）:

```
https://<GitHubのID>.github.io/KRnameCompatibility/
```

---

## ディレクトリ構成

```
KRnameCompatibility/
├── README.md / README.ko.md          このドキュメント（設計の確定内容を含む）
├── DEPLOY.md / DEPLOY.ko.md          AWS デプロイ手順（EC2/RDS/SG/HTTPS/Datadog）
├── GITHUB_PAGES.md / .ko.md          GitHub Pages 公開手順
├── docker-compose.yml                app + nginx + mysql(local) + datadog
├── .env.example                      環境変数テンプレート
├── preview.html                      サーバー不要の UI 確認用（自動生成）
│
├── backend/
│   ├── app.py                        Flask アプリ・ルーティング・エラーハンドリング
│   ├── wsgi.py                       gunicorn エントリポイント
│   ├── config.py                     環境変数の設定
│   ├── hangul.py                     字母分解 + 画数表（アルゴリズムの確定箇所）
│   ├── compatibility.py              相性アルゴリズム + 計算過程の生成
│   ├── db.py                         MySQL(RDS) アクセス（保存・ランキング・削除）
│   ├── fortune.py                    外部 Fortune API 連携 + フォールバック
│   ├── logging_setup.py              JSON 構造化ログ（Datadog 連携）
│   ├── devserver.py                  依存なしの開発サーバー
│   ├── gunicorn.conf.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/test_core.py            ユニットテスト
│
├── frontend/
│   ├── index.html                    日本語 UI
│   ├── css/style.css
│   └── js/
│       ├── app.js                    API 呼び出し・結果描画・計算過程・削除
│       └── kana2hangul.js            カタカナ → ハングル変換（日本人向け入力補助）
│
├── nginx/
│   ├── 00-upstream.conf              upstream + rate limit + log_format（http コンテキスト）
│   └── default.conf                  リバースプロキシ + 静的配信 + JSON アクセスログ
│
├── db/init.sql                       スキーマ
├── datadog/
│   ├── conf.d/nginx.d/conf.yaml
│   ├── conf.d/mysql.d/conf.yaml.example  ← 複製して conf.yaml を作る（git 対象外）
│   ├── conf.d/http_check.d/conf.yaml
│   └── monitors.md / monitors.ko.md  モニター・ダッシュボード・トレース設計
├── docs/index.html                   GitHub Pages 用の静的版（自動生成）
└── tools/
    ├── mock-api.js                   preview 用のモック API
    ├── static-api.js                 GitHub Pages 用の静的 API（localStorage）
    ├── build_preview.py              preview.html 生成
    └── build_static.py               docs/index.html 生成
```

---

## 確定したアルゴリズム

画数の数え方には複数の流派があるため、**このプロジェクトのルールを一箇所に固定**しました。
表は `backend/hangul.py` にのみ存在し、すべての計算がそれを参照します。
したがって同じ入力からは常に同じ結果が出ます。

### 画数表

**子音**

| ㄱ | ㄴ | ㄷ | ㄹ | ㅁ | ㅂ | ㅅ | ㅇ | ㅈ | ㅊ | ㅋ | ㅌ | ㅍ | ㅎ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 2 | 3 | 5 | 4 | 4 | 2 | 1 | 3 | 4 | 3 | 4 | 4 | 3 |

**母音**

| ㅏ | ㅐ | ㅑ | ㅒ | ㅓ | ㅔ | ㅕ | ㅖ | ㅗ | ㅘ | ㅙ | ㅚ | ㅛ | ㅜ | ㅝ | ㅞ | ㅟ | ㅠ | ㅡ | ㅢ | ㅣ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 3 | 3 | 4 | 2 | 3 | 3 | 4 | 2 | 4 | 5 | 3 | 3 | 2 | 4 | 5 | 3 | 3 | 1 | 2 | 1 |

**濃音・二重パッチム**は構成する子音の合計として定義します。
`ㄲ=4, ㄸ=6, ㅃ=8, ㅆ=4, ㅉ=6` / `ㄳ=4, ㄵ=5, ㄶ=5, ㄺ=7, ㄻ=9, ㄼ=9, ㄽ=7, ㄾ=9, ㄿ=9, ㅀ=8, ㅄ=6`

### 計算の手順

```
STEP 1  音節 → 初声/中声/終声に分解し、音節ごとの画数を合計
        심효진 → 심(ㅅ2+ㅣ1+ㅁ4=7) 효(ㅎ3+ㅛ3=6) 진(ㅈ3+ㅣ1+ㄴ2=6) = [7, 6, 6]
        야마다 → [4, 6, 5]

STEP 2  ふたつの配列を交互に並べる（常に 심효진 が先）
        [7, 4, 6, 6, 6, 5]
        長さが異なる場合、短い方が尽きた後に残りをそのまま後ろへ追加する。

STEP 3  隣り合う数を足し、10 以上なら 1 の位だけを残す。長さ 2 になるまで繰り返す。
        [7, 4, 6, 6, 6, 5]
        [1, 0, 2, 2, 1]
        [1, 2, 4, 3]
        [3, 6, 7]
        [9, 3]

STEP 4  残った 2 つの数を十の位・一の位として読む → 93%
```

計算の中間ステップはすべて API レスポンスの `steps` に含まれ、
画面の「どんな仕組み？」でそのまま表示されます。

### スコアの区分

| スコア | 等級 |
|---|---|
| 90+ | 運命級 |
| 80+ | 大吉 |
| 70+ | 吉 |
| 60+ | 中吉 |
| 50+ | 小吉 |
| 40+ | 末吉 |
| 20+ | がんばれ |
| 0+ | ドンマイ |

---

## カタカナ入力の補助

日本のユーザーは韓国語キーボードを持っていません。そのためフロントエンドに
`カタカナ / ひらがな → ハングル` の変換機能を入れました（`frontend/js/kana2hangul.js`）。
韓国の外来語表記法に近いルールに従います。

| 入力 | 出力 | 適用ルール |
|---|---|---|
| たなか | 다나카 | カ行・タ行は語頭では平音（가/다） |
| さとう | 사토 | 長母音（おう）は表記しない |
| こんどう | 곤도 | ん → ㄴ パッチム + 長母音の省略 |
| はっとり | 핫토리 | っ → ㅅ パッチム |
| つじ | 쓰지 | つ は常に 쓰 |
| ヒョウドウ | 효도 | 拗音 + 長母音の省略 |

変換結果はユーザーが直接修正できます。最終的な検証はサーバー側で再度行います。

---

## API

| Method | Path | 説明 |
|---|---|---|
| GET | `/api/health` | ヘルスチェック（DB 状態を含む） |
| GET | `/api/meta` | 自分の名前、統計 |
| POST | `/api/compatibility` | 相性診断 |
| GET | `/api/ranking?limit=20` | ランキング（score DESC） |
| DELETE | `/api/ranking` | ランキング全削除 |
| DELETE | `/api/ranking/{名前}` | 特定の名前の記録を削除 |
| GET | `/api/fortune` | フォーチュンクッキー（外部 API） |
| GET | `/api/stroke-table` | 画数表 |

削除 API は `ADMIN_TOKEN` 環境変数が設定されている場合、`X-Admin-Token` ヘッダーを要求します。
空（デフォルト）なら認証なし — SSH トンネル経由のみでアクセスする個人環境を前提としているため、
外部に公開する際は必ず値を設定してください。

### POST /api/compatibility

```json
// Request
{ "partner_name": "야마다" }

// Response 200
{
  "owner_name": "심효진",
  "partner_name": "야마다",
  "score": 93,
  "grade": { "label": "運命級", "comment": "これはもう運命。..." },
  "steps": {
    "step1_decompose": {
      "owner":   [{ "char": "심", "strokes": 7,
                    "jamos": [{ "char": "ㅅ", "role": "chosung",
                                "role_label": "初声(子音)", "strokes": 2 }] }],
      "partner": []
    },
    "step2_strokes":     { "owner": [7, 6, 6], "partner": [4, 6, 5] },
    "step3_interleaved": [7, 4, 6, 6, 6, 5],
    "step4_reduction":   [[7,4,6,6,6,5], [1,0,2,2,1], [1,2,4,3], [3,6,7], [9,3]],
    "step5_score": 93
  },
  "saved": true
}
```

エラーは `400` と日本語メッセージを返します。

```json
{ "error": "NOT_HANGUL", "message": "ハングル（한글）で入力してください。例: 야마다" }
```

`EMPTY` / `NOT_HANGUL` / `LENGTH` の 3 種類で、完成形ハングル 2〜8 文字のみを通します。

---

## データベース

```sql
compatibility_results
  id            BIGINT UNSIGNED PK
  owner_name    VARCHAR(20)      -- 심효진
  partner_name  VARCHAR(20)
  score         TINYINT UNSIGNED
  grade_label   VARCHAR(32)
  detail        JSON             -- 計算過程すべて
  lookup_count  INT UNSIGNED     -- 参照回数
  created_at    DATETIME
  updated_at    DATETIME
  UNIQUE (owner_name, partner_name)
  KEY (score DESC, created_at ASC)
```

`(owner_name, partner_name)` に UNIQUE を張り、UPSERT します。
同じ入力なら必ず同じスコアになるため行を増やす理由がなく、ランキングに同じ人が重複表示されません。
代わりに `lookup_count` で人気度を数えます。

---

## 障害時の挙動（graceful degradation）

学習用プロジェクトではありますが、観測に値する状態を作るには失敗時の扱いを明確にする必要があります。

| 失敗箇所 | サービスの挙動 | 残るシグナル |
|---|---|---|
| RDS ダウン | スコアの計算・表示は正常、保存のみ失敗（`saved: false`） | `db.save_result_failed` ログ、`/api/health` → `db: down` |
| RDS ダウン（ランキング） | ランキングのみ `503` | `ranking.query_failed` ログ |
| 外部 Fortune API のダウン・遅延 | 3 秒タイムアウト後にローカルメッセージへ切替 | `fortune.api_failed` ログ、レスポンスの `source: "fallback"` |
| アプリのダウン | Nginx 502 | `http_check` CRITICAL |

---

## ローカル開発

```bash
# 1) コアロジックのテスト
cd backend
python3 -m pytest -q

# 2) 依存なしの開発サーバー（ランキングはメモリ）
python3 devserver.py

# 3) Flask で実行（DB なし）
pip install -r requirements.txt
DB_ENABLED=false python3 app.py

# 4) Docker フルスタック
docker compose --profile local up -d --build

# 5) preview.html の再生成
python3 tools/build_preview.py
```

---

## GitHub Pages 静的版

サーバーなしでブラウザだけで動く版も同梱しています。同僚にリンク 1 本で共有するときに使います。

```bash
python3 tools/build_static.py     # docs/index.html を生成
open docs/index.html              # ローカル確認
```

相性アルゴリズムは EC2 版と同一に実装してあり、**スコアは常に一致します**
（検証済み: 야마다 93%、타나카 93%、사토 36%、스즈키 79%、와타나베 62%、이토 74%、코바야시 68%）。
違いはランキングの保存先だけです — RDS（全員で共有）か localStorage（ブラウザごと）か。

公開手順は [`GITHUB_PAGES.md`](GITHUB_PAGES.md) を参照してください。

> **注意**: 秘密情報を含むファイルは `.gitignore` に登録済みです。
> push の前に `git status --short` で必ず確認してください。
>
> | ファイル | 中身 | git |
> |---|---|---|
> | `.env` | Datadog API キー、RDS パスワード | 対象外 |
> | `datadog/conf.d/mysql.d/conf.yaml` | datadog DB ユーザーのパスワード | 対象外 |
> | `datadog/conf.d/mysql.d/conf.yaml.example` | プレースホルダーのみ | 管理する |
> | `frontend/js/rum.js` の `clientToken` | 公開前提の値（`pub` 接頭辞） | 管理してよい |

## CloudWatch との比較

同じ EC2 を CloudWatch Agent と Datadog Agent の両方で観測し、違いを確かめる構成も用意しています。

```bash
# cloudwatch/amazon-cloudwatch-agent.json を EC2 に置いて起動
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

CloudWatch は標準では **EC2 のメモリを提供しません**。Agent を入れる最大の理由がそこにあります。
手順と比較のポイントは [`CLOUDWATCH.md`](CLOUDWATCH.md) を参照してください。

## 次のステップ

デプロイは [`DEPLOY.md`](DEPLOY.md)、モニタリング・トレース設計は
[`datadog/monitors.md`](datadog/monitors.md)、
CloudWatch との比較は [`CLOUDWATCH.md`](CLOUDWATCH.md) を参照してください。
