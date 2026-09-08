[한국어](monitors.ko.md) | **日本語**

# Datadog モニター / ダッシュボード / トレース設計

設計書 8 章の観測対象を実際の設定に落としたもの。Datadog の UI でそのまま作成できます。

## 1. 収集経路の整理

| 観測対象 | 収集方法 | 主なメトリクス |
|---|---|---|
| EC2 (CPU/Mem/Disk/Net) | Datadog Agent（標準の system check） | `system.cpu.user`, `system.mem.pct_usable`, `system.disk.in_use`, `system.net.bytes_rcvd` |
| Nginx のリクエスト/レスポンス | nginx integration (`stub_status`) + JSON アクセスログ | `nginx.net.request_per_s`, `nginx.net.connections`, ログの `request_time` |
| Application | ddtrace (APM) + 構造化ログ | `trace.flask.request.hits/errors/duration` |
| **DB クエリ** | ddtrace の pymysql 自動計装 | `trace.pymysql.query.duration` |
| 外部 Fortune API | アプリログ（`fortune.api_call` / `fortune.api_failed`）+ http_check | ログベースのメトリクス |
| RDS | mysql integration + CloudWatch (AWS integration) | `mysql.performance.queries`, `mysql.net.connections`, `aws.rds.cpuutilization`, `aws.rds.free_storage_space` |

## 1-2. APM トレースと DB スパン（トレース ↔ ログ ↔ クエリ）

`ddtrace-run` が Flask と **pymysql を自動計装** するため、コードを書かずに
1 リクエストが次のようなトレースとして記録されます。

```
flask.request  POST /api/compatibility          12.4ms
├─ flask.dispatch                                11.8ms
│  └─ pymysql.query  INSERT INTO compatibility…   8.2ms   ← DB スパン
└─（fortune 呼び出し時）requests.request          3.1ms   ← 外部 API スパン
```

これを作っているのが `docker-compose.yml` の app サービスに設定した環境変数です。

| 環境変数 | 役割 |
|---|---|
| `DD_TRACE_ENABLED=true` | トレーシング有効化 |
| `DD_TRACE_SAMPLE_RATE=1.0` | 100% 収集（トラフィックの少ない学習環境向け） |
| `DD_LOGS_INJECTION=true` | ログに `dd.trace_id` を注入 → ログ↔トレースを相互に移動 |
| `DD_DBM_PROPAGATION_MODE=full` | APM スパン ↔ DBM クエリの紐付け |
| `DD_SERVICE_MAPPING=mysql:name-compat-db` | サービスマップで DB を別ノードとして表示 |

### 確認する場所

| 見たいもの | Datadog UI |
|---|---|
| 1 リクエストの全体の流れ | APM → Traces → `name-compat-api` → トレースをクリック |
| そのリクエストが投げた SQL | トレース内の `pymysql.query` スパン → Tags の `sql.query` |
| このリクエストが残したログ | トレース詳細の下部 **Logs** タブ（trace_id で自動フィルタ） |
| DB がボトルネックか | APM → Service Page → `name-compat-api` → Dependencies |
| クエリ別の性能・実行計画 | Databases → `name-compat-db`（**DBM が必要**） |

### DB はどこまで見えるか — 3 段階

| 段階 | 必要なもの | 見えるもの |
|---|---|---|
| **① DB スパン**（すでに動作中） | なし。ddtrace の自動計装 | リクエスト別の SQL、クエリ所要時間、N+1 の発見 |
| **② RDS メトリクス** | `mysql.d/conf.yaml` に datadog アカウントを設定 | Connections, Slow_queries, InnoDB, スキーマサイズ |
| **③ DBM** | ＋ RDS パラメータグループ（`performance_schema=1` 等）＋ `dbm: true` | クエリ別の実行時間分布、実行計画 (EXPLAIN)、待機イベント |

① は今すぐ見えます。② は `datadog/conf.d/mysql.d/conf.yaml` 冒頭のコメントにある SQL を実行し、
エンドポイントとパスワードを埋めるだけです。③ はパラメータグループを新規作成して RDS を再起動する
必要があるため、② を確認してから余裕のあるときに追加するのを勧めます。

### このプロジェクトでトレースを見る価値があるもの

- `POST /api/compatibility` は計算（純粋な CPU）と `INSERT`（DB）が同じトレースに並んで入ります。
  → 実際に時間を食っているのが DB 側だと目で確認できます。
- `GET /api/fortune` には外部 API スパンが付きます。外部が遅くなるとトレースの幅が 3 秒に伸びます。
- `DELETE /api/ranking` は単一の DELETE スパン。削除件数はログの `@deleted` に残ります。

## 2. ログベースのカスタムメトリクス (Logs → Generate Metrics)

アプリが出す JSON ログをそのままメトリクスにできます。

| メトリクス名 | クエリ | 用途 |
|---|---|---|
| `namecompat.diagnosis.count` | `service:name-compat-api "compatibility.calculated"` | 診断回数 |
| `namecompat.diagnosis.score` | 同上、measure = `@score` | 平均スコアの分布 |
| `namecompat.fortune.fallback` | `service:name-compat-api "fortune.opened" @source:fallback` | 外部 API の失敗率 |
| `namecompat.validation.error` | `service:name-compat-api "compatibility.validation_failed"` | 入力エラー（= UX の問題）の追跡 |
| `namecompat.db.save_failed` | `service:name-compat-api "db.save_result_failed"` | DB 保存の失敗 |
| `namecompat.ranking.deleted` | `service:name-compat-api "ranking.deleted*"`, measure = `@deleted` | 削除件数 |

## 3. モニターの定義

### 3-1. サービスダウン
```
service check: http_check.status
  over: instance:name-compat-health
  alert if CRITICAL for 2 consecutive checks
```
> メッセージ例: `名前相性診断が応答していません @slack-my-channel`

### 3-2. アプリのエラー率
```
avg(last_5m):
  ( sum:trace.flask.request.errors{service:name-compat-api}.as_count()
    / sum:trace.flask.request.hits{service:name-compat-api}.as_count() ) * 100
> 5      (warning: 2)
```

### 3-3. レスポンスタイム (p95)
```
avg(last_10m): p95:trace.flask.request.duration{service:name-compat-api} > 1
```

### 3-4. DB クエリの遅延
```
avg(last_10m): p95:trace.pymysql.query.duration{service:name-compat-api} > 0.5
```

### 3-5. EC2 のリソース
```
avg(last_10m): avg:system.cpu.user{host:hyojin-ubuntu} > 80
avg(last_5m):  avg:system.mem.pct_usable{host:hyojin-ubuntu} < 0.15
avg(last_5m):  avg:system.disk.in_use{host:hyojin-ubuntu,device:/dev/root} > 0.85
```

### 3-6. RDS
```
avg(last_10m): avg:aws.rds.cpuutilization{dbinstanceidentifier:hyojin-db} > 80
avg(last_10m): avg:aws.rds.database_connections{dbinstanceidentifier:hyojin-db} > 40
avg(last_15m): avg:aws.rds.free_storage_space{dbinstanceidentifier:hyojin-db} < 2000000000
```

### 3-7. 外部 API の劣化（フォールバック比率）
```
sum(last_15m): sum:namecompat.fortune.fallback{*}.as_count() > 10
```
> 外部 API が落ちてもサービスは生きていますが、「なぜメッセージが単調なのか」を説明してくれます。

## 4. ダッシュボードのウィジェット構成（推奨順）

1. **Top row (Status)** — http_check の状態、本日の診断回数、平均スコア
2. **Application** — Requests/s、Error rate、Latency p50/p95/p99 (APM)
3. **Trace** — Service Map (api → db → external)、遅いトレースの一覧
4. **Nginx** — Requests/s、Active connections、ステータスコード別のログ件数
5. **EC2** — CPU / Memory / Disk / Network
6. **RDS** — CPU、Connections、Free storage、Slow queries
7. **Business** — スコア分布のヒストグラム、入力エラー (validation_failed) の推移
8. **External** — Fortune API のレスポンスタイム（ログの `duration_ms`）、フォールバック件数

## 5. 実習シナリオ（あえて障害を起こしてみる）

| シナリオ | 方法 | 確認すること |
|---|---|---|
| アプリのダウン | `docker compose stop app` | http_check CRITICAL、Nginx 502 の急増 |
| DB のダウン | RDS のセキュリティグループから 3306 のインバウンドを削除 | `db.save_result_failed` ログ、`/api/health` が degraded、トレースの DB スパンがエラー |
| 外部 API の障害 | `.env` の `FORTUNE_API_URL` を誤った値にして `--force-recreate app` | `fortune.api_failed` ログ、フォールバックのメトリクス上昇 |
| DB の遅延 | `SELECT SLEEP(3)` を投げてみる | トレースで pymysql スパンが伸びるのを見る |
| 負荷 | `ab -n 2000 -c 50 http://localhost/api/ranking` | p95 latency、Nginx 429 (rate limit)、EC2 CPU |

各シナリオの後に **APM → Traces** でその時間帯のトレースを開くと、
どのスパンで時間が伸びたか / どこでエラーが出たかが色で示されます。
ここが Observability 学習の核心です。
