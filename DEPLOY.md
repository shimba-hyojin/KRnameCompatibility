[한국어](DEPLOY.ko.md) | **日本語**

# AWS デプロイガイド

EC2 + Nginx + Docker + RDS + Datadog。上から順に進めれば完了します。
リージョンは `ap-northeast-1`（東京）を前提。想定コストは t3.micro + db.t4g.micro で月 20〜30 USD
（無料利用枠が適用されればほぼ 0）。

**実際に構築したリソース**

| 種類 | 名前 |
|---|---|
| EC2 | `hyojin-ubuntu` (Ubuntu 24.04, t3.micro) |
| EC2 セキュリティグループ | `hyojin-ubuntu-sg` |
| RDS | `hyojin-db` (MySQL 8.0, db.t4g.micro) |
| RDS セキュリティグループ | `hyojin-db-sg` |
| キーペア | `hyojin-key.pem` |
| 初期データベース | `namecompat` |

---

## 0. 全体構成

```
                    Internet
                       │
                  (80 / 443)
                       ▼
        ┌──────────────────────────────┐
        │  EC2  (Ubuntu 24.04, t3.micro)│
        │                              │
        │  ┌────────┐   ┌────────────┐  │
        │  │ Nginx  │──▶│ Flask app  │  │   Docker Compose
        │  │ :80    │   │ :8000      │  │
        │  └────────┘   └─────┬──────┘  │
        │  ┌──────────────────┴───────┐ │
        │  │  Datadog Agent           │ │
        │  └──────────────────────────┘ │
        └──────────────┬───────────────┘
                       │ 3306（VPC 内部のみ）
                       ▼
              ┌─────────────────┐         ┌──────────────────┐
              │ RDS for MySQL   │         │ Fortune API      │
              │ db.t4g.micro    │         │ jugemkey.jp      │
              └─────────────────┘         └──────────────────┘
```

重要な原則が 2 つあります。

1. **RDS のパブリックアクセスは切る。** EC2 のセキュリティグループのみ 3306 を許可する。
2. **アプリコンテナは外部にポートを開けない。** Nginx だけが 80/443 を持つ。

---

## 1. セキュリティグループを先に作る

リソースより先にセキュリティグループを作っておくと後で迷いません。

### 1-1. `hyojin-ubuntu-sg` (EC2 用)

EC2 インスタンス起動画面の「ネットワーク設定 → 編集 → セキュリティグループを作成」で
ルールまで一度に作れます。

| 方向 | タイプ | ポート | ソース | 説明 |
|---|---|---|---|---|
| インバウンド | SSH | 22 | **マイ IP** | 0.0.0.0/0 は絶対に避ける |
| インバウンド | HTTP | 80 | (1-3 参照) | 社内ポリシーによって異なる |
| アウトバウンド | すべて | すべて | 0.0.0.0/0 | 外部 API・Datadog・apt |

### 1-2. `hyojin-db-sg` (RDS 用) — **RDS 作成画面で作る**

| 方向 | タイプ | ポート | ソース |
|---|---|---|---|
| インバウンド | MYSQL/Aurora | 3306 | **`hyojin-ubuntu-sg`**（セキュリティグループ参照） |

ソースに IP ではなく **セキュリティグループ ID を入れる** のがポイントです。
EC2 を差し替えてもルールを直す必要がありません。

ただしこのルールは `hyojin-ubuntu-sg` が既に存在しないと入れられません。順序はこうします。

1. EC2 を先に作って `hyojin-ubuntu-sg` を生成する → 3 章
2. RDS 作成画面の「接続」セクションで **VPC セキュリティグループ → 新規作成**、名前 `hyojin-db-sg`
3. RDS の作成が終わった後に `hyojin-db-sg` のインバウンドルールを上の表の通り追加する

> **落とし穴**: RDS 作成画面で SG を新規作成すると、AWS が自動で「自分のノート PC のパブリック IP/32」を
> インバウンドに入れます。このルールはパブリックアクセスを切った RDS では何の役にも立たず、
> EC2（プライベート IP）から来るトラフィックとも一致しないためタイムアウトします。
> **削除して SG 参照に置き換えます。**

### 1-3. 社内アカウントで `0.0.0.0/0` が自動削除される場合

多くの企業がセキュリティツール（AWS Config / Security Hub / 自作の remediation Lambda）で
**広範な CIDR のインバウンドルールを自動的に回収** します。1-1 の `HTTP 80 ← 0.0.0.0/0` が
追加直後に消えたなら、ポリシーが正常に動作したということです。回避せず、以下のいずれかを使います。

#### 方法 A. SSH ポートフォワーディング ← **このプロジェクトで採用**

自分だけが見る、または画面共有で見せる用途なら 80 を開ける必要はまったくありません。
SSH トンネルでローカルに引き込めば、ブラウザからはローカルサイトのように見えます。

`~/.ssh/config` に一度登録しておくとコマンドが短くなります。

```sshconfig
Host nc
    HostName <EC2_PUBLIC_IP>
    User ubuntu
    IdentityFile ~/.ssh/hyojin-key.pem
    LocalForward 8888 localhost:80
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

以降:

```bash
ssh nc                    # トンネル + シェルを同時に
ssh -fN nc                # トンネルだけバックグラウンドで
```

ブラウザで `http://localhost:8888` にアクセス。
Nginx・Flask・RDS・Datadog はすべて正常に動作し、外部からアクセスできるポートは 1 つもありません。

> ポートが既に使用中だと `bind: Address already in use` が出ます。
> `lsof -i :8888` で確認するか、別のポートを使います。

トンネルが切れるとブラウザが接続拒否を返します。`ssh nc` を再実行すれば戻ります。
頻繁に切れるなら `brew install autossh` の後 `autossh -M 0 -fN nc`。

#### 方法 B. 会社の IP レンジに絞る

社内だけで使うサービスなら、ソースを会社のエグレス CIDR に指定します。
正確なレンジはネットワーク / IT チームに確認します。

#### 方法 C. SSM Session Manager（インバウンド 22 も不要）

もっともポリシーに優しい方法。Ubuntu AMI には SSM Agent が既に入っています。

1. EC2 に `AmazonSSMManagedInstanceCore` ポリシーを持つ IAM ロールを紐付ける
2. ローカルで:

```bash
aws ssm start-session --target <INSTANCE_ID> \
  --document-name AWS-StartPortForwardingSession \
  --parameters 'portNumber=80,localPortNumber=8888'
```

#### 方法 D. 同僚に公開する必要があるとき

日本の同僚に実際に使ってもらうには、社内で承認された公開経路が必要です。
通常は **内部 ALB + 社内ネットワーク/VPN**、または会社が運用するリバースプロキシへの登録です。
これはセキュリティ / インフラチームと相談すべき項目で、勝手に SG を開けて解決する問題ではありません。

---

## 2. RDS for MySQL の作成

コンソール → RDS → データベースの作成。記載のない項目はデフォルトのままにします。

| セクション | 項目 | 値 |
|---|---|---|
| ① | 作成方法 | **標準作成**（簡易作成では SG・初期 DB を指定できない） |
| ② | エンジン | MySQL 8.0.x |
| ③ | テンプレート | 無料利用枠（無い場合は開発/テスト + db.t4g.micro） |
| ④ | DB インスタンス識別子 | `hyojin-db` |
| ④ | マスターユーザー | `admin` |
| ④ | マスターパスワード | 直接入力 → **別途保管** |
| ⑤ | インスタンスクラス | db.t4g.micro |
| ⑥ | ストレージ | gp3 20GB、**自動スケーリングのチェックを外す**（課金事故の防止） |
| ⑦ | パブリックアクセス | **なし** |
| ⑦ | VPC セキュリティグループ | **新規作成** → 名前 `hyojin-db-sg` |
| ⑧ | **初期データベース名** | `namecompat` ← **「追加設定」の中に隠れている** |
| ⑧ | バックアップ保持期間 | 1 日（学習用） |

⑧ を空にすると空のサーバーだけができ、後で手動で `CREATE DATABASE` する必要があります。

作成後、**エンドポイント** をコピーしておきます（接続とセキュリティ タブ）。
例: `hyojin-db.c1mmuwo2mx97.ap-northeast-1.rds.amazonaws.com`

ステータスが `作成中` → `バックアップ中` → **`利用可能`** になるまで 10〜15 分。その間に 3 章を進めます。

### 2-1. 文字セットの確認

韓国語 / 日本語を安全に保存するには utf8mb4 が必要です。RDS MySQL 8.0 はデフォルトで utf8mb4 です。

```sql
SHOW VARIABLES LIKE 'character_set_server';   -- utf8mb4 を期待
SHOW VARIABLES LIKE 'collation_server';
```

---

## 3. EC2 インスタンスの作成

| セクション | 項目 | 値 |
|---|---|---|
| ① | 名前 | `hyojin-ubuntu` |
| ② | AMI | Ubuntu Server 24.04 LTS、**64 ビット (x86)** |
| ③ | インスタンスタイプ | t3.micro |
| ④ | キーペア | **新しいキーペアの作成** → `hyojin-key`、RSA、`.pem` |
| ⑤ | パブリック IP の自動割り当て | 有効化 |
| ⑤ | ファイアウォール | セキュリティグループを作成 → `hyojin-ubuntu-sg`（ルールは 1-1） |
| ⑥ | ストレージ | **20 GiB** gp3（デフォルトの 8GiB は Docker イメージですぐ埋まる） |
| ⑦ | | インスタンスを起動 |

> **キーペアはたった一度しかダウンロードできません。** 失くすとこのインスタンスに永久にアクセスできません。
> 受け取ったらすぐ安全な場所に移動します。

### 3-1. 接続

```bash
mv ~/Downloads/hyojin-key.pem ~/.ssh/
chmod 400 ~/.ssh/hyojin-key.pem
ssh -i ~/.ssh/hyojin-key.pem ubuntu@<EC2_PUBLIC_IP>
```

プロンプトが `ubuntu@ip-172-31-x-x:~$` に変われば成功です。

**よく出るエラー**

| メッセージ | 原因 |
|---|---|
| `Permission denied (publickey)` | `-i` を付けていない、キーのパスが違う。Ubuntu のユーザー名は `ubuntu`（ec2-user ではない） |
| `Identity file ... No such file` | キーがまだ Downloads にある → `mv` |
| `UNPROTECTED PRIVATE KEY FILE` | `chmod 400` をしていない |
| `Connection timed out` | SSH 22 のソースが現在の IP と違う → セキュリティグループを更新 |

> IP が再起動ごとに変わるのが嫌なら Elastic IP を割り当てます（紐付けたまま使えば無料）。

---

## 4. EC2 の初期設定

```bash
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone Asia/Tokyo
sudo apt install -y git curl vim mysql-client-core-8.0
```

`apt upgrade` 中に青い画面（サービス再起動の確認）が出たら Enter。

### 4-0. スワップの追加 — t3.micro では実質必須

t3.micro のメモリは約 950MB しかありません。Datadog Agent（200〜300MB）を起動した状態で
`ddtrace` のような C 拡張パッケージをビルドするとメモリが足りず **ビルドが止まります**
（エラーも出ず pip のダウンロード途中でそのまま停止）。スワップを先に用意しておけばこの問題は起きません。

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -m        # Swap: 2047 を確認
```

`/etc/fstab` に登録したので再起動後も維持されます。

ビルドがそれでも重いなら Agent を一時的に止めてビルドします。

```bash
docker compose stop datadog
docker compose build app
docker compose up -d
docker compose --profile datadog up -d
```

### 4-1. Docker / Docker Compose のインストール

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
                    docker-buildx-plugin docker-compose-plugin

# sudo なしで docker を使う（再ログインが必要）
sudo usermod -aG docker ubuntu
exit
```

**Mac に戻ってから** 再度接続して確認します（EC2 の中でもう一度 ssh を打つのは誤りです）。

```bash
ssh -i ~/.ssh/hyojin-key.pem ubuntu@<EC2_PUBLIC_IP>
docker run --rm hello-world     # sudo なしで通れば成功
```

> 今どこにいるか分からなくなったら `hostname`。`ip-172-31-...` なら EC2 の中です。

---

## 5. RDS への接続確認

EC2 から RDS に繋いでみます。ここで詰まったら **セキュリティグループ** か **VPC** を見直します。

```bash
# ポートだけを素早く確認（mysql クライアントなしで）
timeout 5 bash -c "cat < /dev/null > /dev/tcp/<RDS_ENDPOINT>/3306" \
  && echo "3306 開いている" || echo "閉じている"

# DNS がプライベート IP に解決されるか（172.31.x.x であるべき）
getent hosts <RDS_ENDPOINT>

mysql -h <RDS_ENDPOINT> -u admin -p -e "SHOW DATABASES;"
```

`namecompat` が一覧にあれば通過です。

| 症状 | 原因 |
|---|---|
| 止まった後 `ERROR 2003 ... (110)` | タイムアウト。`hyojin-db-sg` に 3306 のルールがない、またはソースが SG 参照でない |
| `Access denied` | パスワードが違う |
| `Unknown MySQL server host` | エンドポイントのタイプミス |
| パブリック IP に解決される | EC2 と RDS が別の VPC にある |

### 5-1. アプリ専用アカウント（任意）

初回起動は `admin` の方が楽です（アプリがテーブルを自動生成するには DDL 権限が必要）。
正常動作を確認した後に権限を絞ります。

```sql
CREATE USER 'appuser'@'%' IDENTIFIED BY '<APP_DB_PASSWORD>';
GRANT SELECT, INSERT, UPDATE, DELETE ON namecompat.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
```

削除機能（`DELETE /api/ranking`）を使うには `DELETE` 権限が必要です。

---

## 6. アプリケーションのデプロイ

### 6-1. コードのアップロード

git リポジトリがあれば `git clone`、なければローカルで圧縮して送ります。

```bash
# Mac 側
cd ~/Downloads
scp -i ~/.ssh/hyojin-key.pem name-compat.tar.gz ubuntu@<EC2_IP>:~/

# EC2 側
cd ~
tar -xzf name-compat.tar.gz
cd name-compat
chmod -R a+rX . && chmod 600 .env    # ← 下の注意を参照
```

> **権限の注意**: 静的ファイルが `600`（所有者のみ読み取り）だと nginx ワーカー (uid 101) が
> 読めず `/` が **404** になります（403 ではなく 404 になるのがこの症状の特徴）。
> `chmod -R a+rX` が必須です。

> **再デプロイ時**: アーカイブの `.env` はローカル用のデフォルト値（`DB_HOST=mysql`）なので、
> 上書きすると DB が切れます。
> ```bash
> cp name-compat/.env /tmp/env.bak
> tar -xzf name-compat.tar.gz
> cp /tmp/env.bak name-compat/.env
> ```

### 6-2. `.env` の作成

```bash
nano .env
```

本番で直す項目:

```ini
APP_ENV=prod
DB_HOST=hyojin-db.c1mmuwo2mx97.ap-northeast-1.rds.amazonaws.com
DB_USER=admin
DB_PASSWORD=<RDS のマスターパスワード>

DD_API_KEY=<DATADOG_API_KEY>
DD_TRACE_ENABLED=true
```

`DB_PORT=3306`、`DB_NAME=namecompat` はそのまま。nano の保存は `Ctrl+O` → Enter → `Ctrl+X`。

```bash
chmod 600 .env
grep -E "^(APP_ENV|DB_HOST|DB_USER|DB_NAME)=" .env    # 確認
```

> `.env` の変更はコンテナの **再作成** が必要です。`restart` では環境変数が変わりません。
> `docker compose up -d --force-recreate app`

### 6-3. 起動

```bash
docker compose up -d --build
docker compose ps
```

`namecompat-app`、`namecompat-nginx` の両方が `Up` になれば OK です。
`namecompat-mysql` は `local` プロファイルなので出てこないのが正常です（RDS を使うため）。

t3.micro ではイメージのビルドに 2〜4 分かかります。

### 6-4. 動作確認

```bash
curl -i localhost/api/health
```

期待値:

```json
{"db":"ok","env":"prod","status":"ok"}
```

`"db":"ok"` が肝心です。これが出れば EC2 → RDS の経路まで生きています。

```bash
curl -s -X POST localhost/api/compatibility \
  -H 'Content-Type: application/json' \
  -d '{"partner_name":"야마다"}' | head -c 250
curl -s localhost/api/ranking
curl -s localhost/api/fortune
```

야마다 は **93%** になるはずです（アルゴリズムが固定なのでローカルテストと同一）。

DB に実際に入ったか:

```bash
source .env
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" namecompat \
  -e "SELECT partner_name, score, grade_label, lookup_count FROM compatibility_results;"
```

### 6-5. ブラウザで見る

1-3 の方法 A の SSH トンネルを使います。

```bash
# Mac のターミナルで
ssh -i ~/.ssh/hyojin-key.pem -L 8888:localhost:80 ubuntu@<EC2_IP>
```

トンネルのウィンドウを開いたままブラウザで `http://localhost:8888`

---

## 7. HTTPS の適用（ドメインがある場合）

ドメインの A レコードを EC2 の Elastic IP に向けた後:

```bash
sudo apt install -y certbot
docker compose stop nginx          # 80 番ポートを一時的に空ける

sudo certbot certonly --standalone -d namecompat.example.com

# docker-compose.yml の nginx ボリュームで letsencrypt のコメントを外す
vim docker-compose.yml
```

`nginx/default.conf` に 443 の server ブロックを追加します。

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name namecompat.example.com;

    ssl_certificate     /etc/letsencrypt/live/namecompat.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/namecompat.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_session_cache   shared:SSL:10m;
    add_header Strict-Transport-Security "max-age=31536000" always;

    root /usr/share/nginx/html;
    index index.html;

    # 以下の location ブロックは 80 の server ブロックと同じものをコピー
}
```

そして 80 の server ブロックの `return 301 https://$host$request_uri;` のコメントを外します。

```bash
docker compose up -d nginx

# 自動更新（毎月 1 日 03:00）
sudo crontab -e
# 0 3 1 * * certbot renew --quiet --pre-hook "docker compose -f /home/ubuntu/name-compat/docker-compose.yml stop nginx" --post-hook "docker compose -f /home/ubuntu/name-compat/docker-compose.yml start nginx"
```

---

## 8. Datadog の連携

### 8-1. Agent の起動（コンテナ方式）

`.env` に `DD_API_KEY` を入れていればプロファイルを追加するだけです。

```bash
docker compose --profile datadog up -d
docker compose exec datadog agent status
```

Datadog UI → Infrastructure → Host Map に `hyojin-ubuntu` が出れば成功です（2〜3 分かかります）。

収集されるもの:

- **EC2 メトリクス**: CPU / Memory / Disk / Network (system check)
- **コンテナログ**: `DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=true`
- **Nginx**: コンテナラベルの Autodiscovery で `stub_status` + access/error log
- **APM + DB スパン**: `ddtrace-run` が Flask と pymysql を自動計装

### 8-2. MySQL / RDS の連携

```bash
nano datadog/conf.d/mysql.d/conf.yaml   # <RDS_ENDPOINT>、パスワードを埋める
docker compose restart datadog
docker compose exec datadog agent check mysql
```

ファイル冒頭のコメントに datadog アカウントの作成 SQL と DBM 用パラメータグループの設定が整理されています。

さらに **AWS Integration** を繋ぐと CloudWatch の RDS メトリクス
（`aws.rds.cpuutilization`、`aws.rds.free_storage_space` など）まで入ってきます。
Datadog UI → Integrations → Amazon Web Services → IAM Role 方式で接続します。

### 8-3. ログのパイプライン

アプリは JSON 1 行のログを stdout に出します。

```json
{"timestamp":"2026-09-03T10:12:33+00:00","status":"info","logger":"app",
 "message":"compatibility.calculated","service":"name-compat-api","env":"prod",
 "partner_name":"야마다","score":93,"grade":"運命級","saved":true,
 "dd.trace_id":"...","dd.span_id":"..."}
```

Datadog の Log Explorer で `service:name-compat-api @score:>90` のようにそのまま検索できます。
`dd.trace_id` が入っているのでログ ↔ APM トレースが相互に繋がります。

モニター / ダッシュボード / トレースの構成は [`datadog/monitors.md`](datadog/monitors.md) に整理しました。

---

## 9. 運用コマンド集

```bash
# 状態
docker compose ps
docker compose logs -f app          # アプリのログ
docker compose logs --tail=30 nginx # Nginx のログ
docker compose exec datadog agent status

# デプロイ（コードの更新）
docker compose up -d --build app
docker compose exec nginx nginx -t   # 設定の構文チェック
docker compose exec nginx nginx -s reload

# nginx の設定だけ変えたとき
docker compose up -d --force-recreate nginx

# 再起動 / 停止
docker compose restart app
docker compose down                  # コンテナを削除（ボリュームは維持）

# ディスクの掃除（EC2 の 20GB はすぐ埋まる）
docker system prune -af --volumes
```

---

## 10. トラブルシューティング

実際に遭遇したものを優先度順に。

| 症状 | 確認すること |
|---|---|
| **`docker compose build` が pip のダウンロード中に止まる** | メモリ不足。`free -m` の `available` が 100MB 未満なら 4-0 のスワップを追加 |
| **`/` が 404**（API は正常） | 静的ファイルの権限。nginx ワーカー (uid 101) が読めない状態 → `chmod -R a+rX ~/name-compat && chmod 600 ~/name-compat/.env` |
| **nginx が Started 直後に落ちる** | `docker compose logs nginx`。`log_format` は `http` コンテキスト専用 — `server` ブロックに入れると起動失敗。`00-upstream.conf` に置く |
| **`curl localhost` が接続拒否** | nginx コンテナが落ちている。上の項目を確認 |
| **RDS のタイムアウト (`2003 ... (110)`)** | `hyojin-db-sg` のインバウンドに 3306 / SG 参照のルールがあるか。AWS が自動追加した `マイIP/32` だけでは駄目 |
| **`/api/health` が `db:down`** | `.env` の `DB_HOST` がまだ `mysql`（ローカルのデフォルト）かもしれない。直した後 `--force-recreate app` |
| **SSH `Permission denied (publickey)`** | `-i` の抜け、キーのパス誤り、または EC2 の中で実行中（`hostname` で確認） |
| **`bind: Address already in use`** | トンネルのポート衝突。`lsof -i :8888` または別のポートを使う |
| **80 のルールが自動削除される** | 会社のセキュリティツール。1-3 節の SSH トンネルに切り替える |
| DB 保存は失敗するがスコアは出る | 意図した挙動（graceful degradation）。`db.save_result_failed` ログを確認 |
| 韓国語が `???` で保存される | テーブル / カラムの charset が utf8mb4 か |
| フォーチュンクッキーが `オフラインメッセージ` | 外部 API の失敗 → フォールバック。`fortune.api_failed` ログを確認 |
| Datadog にホストが出ない | `DD_API_KEY`、`DD_SITE`（EU は datadoghq.eu）、アウトバウンド 443 |
| APM トレースが出ない | `DD_TRACE_ENABLED=true`、`DD_AGENT_HOST=datadog`、CMD が `ddtrace-run` |
| 429 Too Many Requests | Nginx の rate limit。`00-upstream.conf` の `rate=10r/s` を調整 |
| ディスクが満杯 | `docker system prune -af` |

---

## 11. 次のステップ（学習の拡張用）

- **CI/CD**: GitHub Actions → ECR へ push → EC2 で `docker compose pull && up -d`
- **ALB + ACM**: certbot の代わりに ALB で TLS 終端、ヘルスチェックは `/api/health`
- **Auto Scaling**: アプリが stateless なので EC2 2 台 + ALB でそのまま拡張できる
- **Datadog Synthetics**: 東京 / ソウルリージョンから実ブラウザテスト
- **RDS Multi-AZ**: フェイルオーバーの実習
- **Secrets Manager**: `.env` の廃止
