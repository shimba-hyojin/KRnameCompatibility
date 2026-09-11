[한국어](CLOUDWATCH.ko.md) | **日本語**

# CloudWatch Agent 設定ガイド

EC2 に CloudWatch Agent を入れて **メモリ・スワップ・ディスク** を収集します。
Datadog Agent と並べて動かし、同じ指標を 2 つのツールがどう扱うかを比較するのが目的です。

---

## 0. なぜ Agent が必要なのか

CloudWatch は EC2 のメトリクスを **ハイパーバイザーの外から** 見ています。そのため分かることに限界があります。

| 指標 | Agent なし（標準） | Agent あり |
|---|---|---|
| CPUUtilization | ✅ | ✅ |
| NetworkIn / NetworkOut | ✅ | ✅ |
| DiskReadBytes（ボリューム I/O） | ✅ | ✅ |
| **メモリ使用率** | ❌ | ✅ |
| **ディスク使用率（ファイルシステム）** | ❌ | ✅ |
| **スワップ使用率** | ❌ | ✅ |

メモリとファイルシステムの使用率は **OS の内側でしか分からない値** です。
AWS は仮想マシンの外にいるので見えません。だから中にプログラム（Agent）を置く必要があります。
Datadog Agent を入れた理由もまったく同じです。

> 実例: `docker compose build` が止まったあのメモリ不足の事件は、**CloudWatch には一切記録されていません。**
> Agent を入れれば、次からはグラフに残ります。

---

## 1. IAM ロールを作る（5 分）

Agent が CloudWatch にデータを送る権限が必要です。
**アクセスキーをサーバーに置かず、IAM ロール** を使います。

コンソール → IAM → ロール → **ロールを作成**

| ステップ | 値 |
|---|---|
| 信頼されたエンティティ | **AWS のサービス** |
| ユースケース | **EC2** |
| 許可ポリシー | `CloudWatchAgentServerPolicy` を検索 → チェック |
| ロール名 | `hyojin-ubuntu-cwagent-role` |

**ロールを作成** をクリック。

### EC2 に紐付ける

EC2 → インスタンス → `hyojin-ubuntu` を選択 → **アクション** → **セキュリティ** → **IAM ロールを変更**
→ 今作ったロールを選択 → **IAM ロールの更新**

再起動は不要です。即座に適用されます。

> **なぜアクセスキーではなくロールなのか**: キーはファイルに書いておく必要があり、漏れたら破棄・再発行が必要です。
> IAM ロールなら EC2 が自動で一時的な認証情報を受け取って使い、期限が来れば失効します。
> サーバーに秘密情報が残りません。

---

## 2. Agent のインストール（5 分）

EC2 に接続して:

```bash
cd ~
wget https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb
```

インストールの確認:

```bash
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a status
```

`"status": "stopped"` と出ます。設定を渡していないので正常です。

---

## 3. 設定ファイルを置く（2 分）

このリポジトリの `cloudwatch/amazon-cloudwatch-agent.json` を EC2 にコピーします。

```bash
sudo cp ~/name-compat/cloudwatch/amazon-cloudwatch-agent.json \
        /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

> リポジトリを EC2 に上げていない場合は、`sudo nano` で内容を直接貼り付けても構いません。

### 設定ファイルがしていること

| 項目 | 値 | 理由 |
|---|---|---|
| `metrics_collection_interval` | 60 秒 | デフォルト。短くすると料金が増える |
| `namespace` | `CWAgent` | コンソールで見つけやすい標準の名前 |
| `append_dimensions` | InstanceId, InstanceType | インスタンス情報をタグのように自動付与 |
| 収集項目 | mem / swap / disk(`/`) の 3 種のみ | **カスタムメトリクスは指標の本数ごとに課金** |

あえて最小にしています。`diskio`、`netstat`、`cpu` の詳細まで有効にすると指標が数十本に増えます。
詳細な観測は Datadog が既に担っているので、CloudWatch には「標準では取れないもの」だけを入れました。

---

## 4. 適用と起動（1 分）

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

`-s` が「設定を読み込んですぐ開始」です。

確認:

```bash
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a status
```

`"status": "running"` なら成功です。

メモリの余裕も一緒に見ます（t3.micro は厳しいです）。

```bash
free -m
```

Datadog Agent（200〜300MB）と CloudWatch Agent（50〜100MB）が同時に動きます。
スワップ 2GB を用意してあるので耐えますが、`available` が常に 50MB 未満なら
CloudWatch Agent を止め、比較だけ終えて片付けた方がよいでしょう。

---

## 5. コンソールで確認（5 分待つ）

CloudWatch → メトリクス → すべてのメトリクス → **CWAgent** → `InstanceId, InstanceType`

| 指標名 | 意味 |
|---|---|
| `MemoryUtilization` | メモリ使用率 % |
| `SwapUtilization` | スワップ使用率 % — 0 より大きければメモリ不足のサイン |
| `DiskUtilization` | ルートボリュームの使用率 % |

最初のデータは 1〜5 分後に現れます。

### 比較の実習

あえてメモリを使わせて、2 つのツールを並べて見ます。

```bash
cd ~/name-compat
docker compose build --no-cache app     # メモリを多く使う作業
```

ビルドが走っている間に:

| ツール | 見る場所 |
|---|---|
| CloudWatch | メトリクス → CWAgent → `MemoryUtilization` |
| Datadog | Infrastructure → Host Map → `hyojin-ubuntu` → Memory |

**違いが見えるポイント**

| | CloudWatch Agent | Datadog Agent |
|---|---|---|
| 収集間隔 | 60 秒（デフォルト） | 15 秒 |
| グラフの反応速度 | 緩やか | 尖った瞬間まで見える |
| プロセス別の内訳 | なし | Live Processes でどのプロセスが使ったか |
| コンテナ別の内訳 | なし | Containers で app/nginx/datadog それぞれ |
| 設定方法 | JSON ファイル + IAM ロール | 環境変数 + API キー |
| 課金方式 | 指標の本数ごと | ホストごと |

**60 秒間隔というのは実際に体感できます。** ビルドのように数十秒で終わるメモリの急上昇は、
CloudWatch では 1〜2 点に丸められ、Datadog では山がはっきり見えます。

---

## 6. アラームを作ってみる（任意、10 分）

収集したメモリ指標でアラームを作ると CloudWatch の真価が出ます。

CloudWatch → アラーム → **アラームの作成**

| ステップ | 値 |
|---|---|
| メトリクスの選択 | CWAgent → `MemoryUtilization`（InstanceId = 自分のインスタンス） |
| 統計 / 期間 | 平均 / 5 分 |
| 条件 | 静的、より大きい、**85** |
| 通知 | 新しい SNS トピックを作成 → 名前 `namecompat-alerts` → **自分のメールアドレス** |
| アラーム名 | `hyojin-ubuntu-memory-high` |

作成直後に **メールで確認依頼** が届きます。リンクを押して承認しないと通知は来ません。

同じ方法で設定しておくと良いもの:

| 指標 | しきい値 |
|---|---|
| `DiskUtilization` | > 85% |
| EC2 `CPUUtilization` | > 80%（Agent 不要、標準指標） |
| RDS `FreeStorageSpace` | < 2GB（Agent 不要） |
| RDS `DatabaseConnections` | > 40（Agent 不要） |

RDS の指標は Agent なしでも存在するので、今すぐ設定できます。

---

## 7. 片付け（試し終わったら）

比較が済んでメモリを節約したい場合:

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a stop
```

完全に削除:

```bash
sudo dpkg -r amazon-cloudwatch-agent
```

IAM ロールは残しておいても料金はかかりません。あとで再利用できます。

**カスタムメトリクスは残っている間ずっと課金される** ので、長く使わないならアラームも一緒に削除する方が良いです。

---

## 8. トラブルシューティング

| 症状 | 原因 / 対処 |
|---|---|
| コンソールに `CWAgent` 名前空間が出ない | 5 分待つ。それでも無ければ IAM ロールが EC2 に付いているか確認 |
| Agent が `stopped` に戻る | ログを確認: `sudo tail -50 /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log` |
| `Unable to retrieve credentials` | IAM ロール未付与。EC2 → アクション → セキュリティ → IAM ロールを変更 |
| JSON のパースエラー | 設定ファイルのカンマ・波括弧を確認。`python3 -m json.tool < ファイル` で検証 |
| メモリがさらに厳しくなった | 正常。Agent が 2 つ動いている。`free -m` を確認し、必要なら 7 番で片付ける |
| `region` 関連のエラー | 設定の `"region": "ap-northeast-1"` が実際のリージョンと一致しているか |

---

## 9. 結論 — 2 つのツールをどう使い分けるか

実際に比較すると、こういう感覚が掴めます。

| 状況 | どちら |
|---|---|
| AWS リソースの状態・料金・上限 | **CloudWatch**（RDS・ELB・Lambda など AWS 自身が知っていること） |
| アプリケーションの中で何が起きたか | **Datadog**（トレース・ログ・プロセス） |
| アラームだけ簡単に設定したい | **CloudWatch**（SNS メールが手軽） |
| 原因を掘り下げる必要がある | **Datadog**（トレース → スパン → ログへ移動） |
| コスト | CloudWatch は指標ごと / Datadog はホストごと |

実務でも両方を併用します。**CloudWatch は AWS インフラの事実の記録**、
**Datadog はサービス挙動の解釈** ぐらいに役割が分かれます。
