[한국어](GITHUB_PAGES.ko.md) | **日本語**

# GitHub Pages 公開ガイド

このプロジェクトを GitHub に上げ、誰でもアクセスできる Web ページとして公開する手順。

---

## 0. 先に知っておくこと

GitHub Pages は **ファイルを配るだけ** の仕組みです。Python を実行してくれるサーバーはありません。

| 構成 | GitHub Pages | 理由 |
|---|---|---|
| HTML / CSS / JS | ✅ | ブラウザが実行する |
| Flask (Python) | ❌ | 実行するサーバーがない |
| RDS (MySQL) | ❌ | DB へ接続できない |
| Nginx | 不要 | GitHub が代わりに配信 |

そのため **静的版** を別に用意しました（`docs/index.html`）。

| 機能 | EC2 版 | GitHub Pages 版 |
|---|---|---|
| 相性計算 | Flask | **ブラウザ**（同じアルゴリズム → 同じスコア） |
| カタカナ変換 | ブラウザ | ブラウザ（同一） |
| 計算過程の表示 | ✅ | ✅ |
| ランキング保存 | RDS（全員で共有） | **localStorage**（訪問者ごと） |
| 削除機能 | ✅ | ✅（自分のブラウザの分だけ） |
| フォーチュンクッキー | 外部 API + フォールバック | ローカルメッセージのみ |
| Datadog による観測 | ✅ | ❌（サーバーがない） |

**ランキングが人によって違って見える** のが最大の違いです。サーバーがないのでデータを集める場所がありません。

---

## 1. ⚠️ 上げる前の必須確認 — 秘密情報

`.env` には **Datadog API キー** と **RDS のパスワード** が入っています。
GitHub に公開されると誰でも見られます。

`.gitignore` に登録済みですが、必ず目で確認してください。

```bash
cd ~/dev/KRnameCompatibility
cat .gitignore          # .env, *.pem があるはず
```

git 初期化後はこう確認します。

```bash
git status --short       # .env が一覧に出なければ正常
git check-ignore -v .env # ".gitignore:1:.env" のように出れば無視されている
```

> **もし誤ってコミットしてしまったら**、ファイルを消しても履歴に残ります。
> その場合は **ただちにキーを破棄して再発行する** のが唯一の解決策です。
> （Datadog: Organization Settings → API Keys / RDS: マスターパスワードの変更）

---

## 2. 静的版の生成

```bash
python3 tools/build_static.py
```

`docs/index.html` と `docs/.nojekyll` が作られます。
フロントエンドを直すたびにこのコマンドを再実行してください。

ローカルで先に確認する:

```bash
open docs/index.html      # macOS — ファイルをそのまま開いても動く
```

---

## 3. GitHub リポジトリを作る

### 3-1. Web で作成

github.com → 右上の **+** → **New repository**

| 項目 | 値 |
|---|---|
| Repository name | `KRnameCompatibility` |
| Description | 韓国式 名前相性診断 (Korean name compatibility) |
| 公開範囲 | **Public** ← Pages を無料で使う条件 |
| Add a README | チェックしない（すでにある） |
| .gitignore / license | 追加しない（すでにある） |

> Private リポジトリでも Pages は使えますが、有料プランが必要です。
> **Public にするとソースコードがすべて公開されます** — だからこそ 1 番の確認が重要です。

### 3-2. ローカルから上げる

```bash
cd ~/dev/KRnameCompatibility

git init
git branch -M main
git add .
git status --short          # .env がないか最終確認！
git commit -m "Initial commit: name compatibility app"

git remote add origin https://github.com/<自分のID>/KRnameCompatibility.git
git push -u origin main
```

`<自分のID>` を実際の GitHub ユーザー名に置き換えます。

**認証を求められたら**: パスワードではなく **Personal Access Token** が必要です。
GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) →
Generate new token → `repo` にチェック → 生成されたトークンをパスワード欄に貼り付け。

（または GitHub CLI: `brew install gh` → `gh auth login` → ブラウザでログイン）

**`error: cannot run gpg` が出たら**: コミット署名が有効なのに `gpg` が入っていない状態です。

```bash
git config commit.gpgsign false      # このリポジトリだけ無効化
```

---

## 4. Pages を有効にする

リポジトリのページ → **Settings** → 左メニューの **Pages**

| 項目 | 値 |
|---|---|
| Source | **Deploy from a branch** |
| Branch | `main` |
| Folder | **`/docs`** ← 重要 |

**Save** をクリック。

1〜3 分後に上部にアドレスが表示されます。

```
https://<自分のID>.github.io/KRnameCompatibility/
```

このアドレスは **誰でも** アクセスできます。日本の同僚にはリンクを送るだけで済みます。

---

## 5. 直して再度上げる

```bash
# フロントエンドを修正した後
python3 tools/build_static.py

git add .
git commit -m "Update UI"
git push
```

push 後 1〜2 分で反映されます。反映が見えないときはブラウザの強制リロード（⌘⇧R）。

デプロイの進行状況はリポジトリの **Actions** タブで確認できます。

---

## 6. EC2 版と併用する

ふたつを同時に運用するのが実際には便利です。

| | 用途 |
|---|---|
| **GitHub Pages** | 同僚へのリンク共有。社内ファイアウォールや SSH トンネルと無関係 |
| **EC2** | Datadog 観測の練習、サーバー運用の練習、本物の DB にデータを溜める |

同じアルゴリズムなので **スコアは一致します**（`야마다` = 93%）。
そのため「静的版で見た結果がサーバー版でも同じ」という確認自体が良い検証になります。

---

## 7. よくある問題

| 症状 | 原因 / 対処 |
|---|---|
| 404 ページ | Folder が `/docs` か確認。`docs/index.html` が push されているか確認 |
| CSS が崩れる | 静的版は CSS が HTML に埋め込まれているため起こらない。崩れたら `build_static.py` を再実行 |
| ランキングが消えた | 正常。localStorage はブラウザごと・シークレットモードで初期化される |
| 他人のランキングが見えない | 正常。サーバーがないため共有されない |
| 修正が反映されない | Actions タブでデプロイ完了を確認 → ブラウザの強制リロード |
| `.env` を上げてしまった | **ただちにキーを破棄して再発行。** 履歴の削除だけでは不十分 |

---

## 8. さらに進めるなら

| やりたいこと | 方法 |
|---|---|
| ランキングを全員で共有 | サーバーが必要 → EC2 版を社内承認された経路で公開、またはサーバーレス（Cloudflare Workers + D1 など） |
| 独自ドメインを使う | Pages 設定の Custom domain + DNS の CNAME |
| アクセス数を見る | GitHub Pages にはない → Datadog RUM か簡易アナリティクスを追加 |
| 自動ビルド | GitHub Actions で push 時に `build_static.py` を自動実行 |
