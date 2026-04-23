# ナビクルスクレイパー — セットアップ & テスト実行手順

ナビクル（おとくる）スクレイパーの初期セットアップと、開発環境でのテスト実行手順をまとめたドキュメントです。

---

## 前提条件

- Docker Desktop が起動できること
- Python 仮想環境（venv）がセットアップ済みであること
- `.env` に認証情報が設定済みであること（後述）

---

## 1. 初回セットアップ

### 1-1. 依存パッケージのインストール

```bash
# Django本体の依存（未インストールの場合）
pip install -r requirements.txt

# スクレイパー固有の依存
pip install -r scraper/requirements.txt
```

### 1-2. .env の確認

プロジェクトルートの `.env` に以下が設定されていることを確認する。

```env
# ナビクル認証情報
NAVIKURU_USERNAME=gigicompany
NAVIKURU_PASSWORD=GIGIgigi1234

# スクレイパー → Django API の内部トークン
SCRAPER_API_TOKEN=a03e241c...

# ポーリング間隔（秒）/ デフォルト: 60
POLL_INTERVAL_SEC=60

# 日次リカバリーの遡り時間（時間）/ デフォルト: 25
RECONCILE_LOOKBACK_HOURS=25
```

---

## 2. テスト実行（通常フロー）

ターミナルを **3つ** 使う。スクレイパーは Django API に POST するため、必ず **Django を先に起動** すること。

### ステップ 1: Docker 起動

```bash
docker compose up -d
```

MySQL コンテナ（`navikuru_mysql`）が起動したことを確認する。

```bash
docker compose ps
```

### ステップ 2: マイグレーション（DB変更があった場合のみ）

```bash
python manage.py migrate
```

> モデル変更がない場合はスキップして問題ない。

### ステップ 3: Django サーバー起動（ターミナル1）

```bash
python manage.py runserver
```

`http://127.0.0.1:8000/` でアクセスできることを確認する。

### ステップ 4: スクレイパー起動（ターミナル2）

```bash
python -m scraper.main
```

起動直後にログインが走り、60秒ごとにナビクル一覧を取得して新着をDBに保存する。

```
# 正常時のログ例
2026-04-22T13:00:00 INFO navikuru [navikuru] ログイン成功
2026-04-22T13:00:01 INFO navikuru [navikuru] 一覧取得開始 (max_pages=1)
2026-04-22T13:00:02 INFO navikuru [navikuru] 50 件取得
2026-04-22T13:00:02 INFO main     [main] 新規登録: 3 件
```

### ステップ 5（任意）: 日次リカバリーバッチ実行（ターミナル3）

過去 25 時間分を遡って取りこぼしを補完したい場合に実行する。実行後は終了する（常駐しない）。

```bash
python -m scraper.reconcile
```

遡り時間を変えたい場合:

```bash
RECONCILE_LOOKBACK_HOURS=48 python -m scraper.reconcile
```

---

## 3. テスト終了（停止手順）

### ステップ 1: スクレイパー停止

ターミナル2 で `Ctrl+C` を押す。

```
2026-04-22T14:00:00 INFO main [main] シグナル 2 受信 — シャットダウン準備中
2026-04-22T14:00:01 INFO main [main] シャットダウン完了
```

### ステップ 2: Django サーバー停止

ターミナル1 で `Ctrl+C` を押す。

### ステップ 3: Docker 停止

```bash
docker compose stop
```

> `down` ではなく `stop` を使うとDBデータが保持される。
> データも含めて完全に消したい場合は `docker compose down -v`。

---

## 4. 各プロセスの役割まとめ

| プロセス | コマンド | 種別 | 役割 |
|---|---|---|---|
| Django サーバー | `python manage.py runserver` | 常駐 | 社内システム本体・スクレイパーAPIの受け口 |
| 監視プロセス | `python -m scraper.main` | 常駐 | 60秒ごとにナビクルを監視・新着をDB保存 |
| 日次リカバリー | `python -m scraper.reconcile` | 1回限り | 取りこぼし補完（cronで1日1回実行） |

---

## 5. よくあるエラー

### `ConnectionError: http://localhost:8000` に接続できない

Django サーバーが起動していない。ステップ 3 を先に実行すること。

### `RuntimeError: ナビクル: ログイン失敗`

`.env` の `NAVIKURU_USERNAME` / `NAVIKURU_PASSWORD` が正しいか確認する。

### `django.db.utils.OperationalError: Can't connect to MySQL`

Docker が起動していない。`docker compose up -d` を実行する。
