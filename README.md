# gigicompany社内システム

## 概要
車買取ビジネスを中心とした業務を統合管理する社内システム。
リード管理（査定申込受付）、営業管理、車両管理、顧客管理、従業員管理、勤怠管理などを一元化。

**現在実装済み:** リード管理（ナビクル査定申込の自動取得・一覧表示）

**詳細な構成は [ARCHITECTURE.md](ARCHITECTURE.md) を参照**

## システム構成
- **Web Framework**: Django 5.0.1
- **Database**: MySQL 8.0（Dockerで起動）
- **Gmail API**: OAuth 2.0方式
- **メール取得方式**: 
  - 🔔 **Push通知（推奨）**: Gmail Pub/Subでリアルタイム検知（コスト削減）
  - 🔄 **ポーリング**: 手動実行またはバックアップ用

### 実装済みアプリ
- **leads (旧:ingest)**: リード管理（査定申込受付）
  - ナビクルからGmail API経由で自動取得
  - 申込情報の一覧表示・検索
  - Push通知による新着検知

### 今後実装予定
- **sales**: 営業管理（商談・契約・売上）
- **vehicles**: 車両管理（買取・在庫・売却）
- **customers**: 顧客管理
- **employees**: 従業員管理
- **attendance**: 勤怠管理
- **dashboard**: 統合ダッシュボード

詳細は [ARCHITECTURE.md](ARCHITECTURE.md) を参照

---

## 環境構築手順（やる順番）

### ✅ Step 1: MySQL起動（Docker）
```powershell
docker-compose up -d
```

### ✅ Step 2: Python仮想環境作成
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### ✅ Step 3: 依存パッケージインストール
```powershell
pip install -r requirements.txt
```

### ✅ Step 4: 環境変数設定
`.env` ファイルを編集（DB接続情報は設定済み）

Googleログインを使う場合は以下も設定してください。

```env
GOOGLE_CLIENT_ID=xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com
ALLOWED_GOOGLE_DOMAIN=gigicompany.jp
```

### ✅ Step 5: Django初期設定
```powershell
python manage.py migrate
python manage.py createsuperuser --username system --email system@gigcompany.jp
```
パスワード入力が求められます：`#1Qazxsw2` を入力

### ✅ Step 6: 開発サーバー起動
```powershell
python manage.py runserver
```
→ WEB画面: http://127.0.0.1:8000/sateiinfo/  
→ 管理画面: http://127.0.0.1:8000/admin/

---

## WEB画面で査定申込一覧を確認する

### 1. 開発サーバーを起動

```powershell
python manage.py runserver
```

### 2. WEB画面にアクセス

ブラウザで以下のURLを開きます：

**http://127.0.0.1:8000/sateiinfo/**

未ログインの場合は **http://127.0.0.1:8000/login/** にリダイレクトされ、
`gigicompany.jp` ドメインのGoogleアカウントのみログイン可能です。

### 3. 主な機能

#### 📊 一覧表示
- **初期表示**: 最新100件を自動表示（DB負荷軽減）
- **検索実行後**: 検索条件にヒットした全件を表示（100件以上も可）
- **総件数表示**: 検索結果の総件数と現在表示中の件数を表示

#### 🔍 検索機能
以下の条件で絞り込み検索が可能：
- **お申込番号**: 完全一致検索
- **お申込日時**: 期間指定（開始日～終了日）
- **住所**: 部分一致検索（例: "東京都"）

#### 📄 ページネーション
- **100件ごとにページ分割**: 大量データも快適に閲覧
- **ページ移動**: 前へ・次へボタン、ページ番号クリックで移動
- **件数表示**: "総件数: X件 (Y～Z件目を表示)"形式で表示

#### 🔔 リアルタイム通知
- **30秒ごとにポーリング**: 新規申込を自動検知
- **ポップアップ通知**: 新規申込があると右上に通知表示
- **クリックでリロード**: 通知をクリックすると最新データに更新

#### 👤 ユーザー情報表示
- **ログインユーザー表示**: 画面右上にユーザー名を表示
- **管理画面リンク**: ヘッダーから管理画面に遷移可能

### 4. システム表示

画面上部に「**gigicompany 社内システム**」と表示され、ロゴマーク（赤と緑のバー）が表示されます。
シンプルで使いやすい社内システムとしてデザインされています。

### 5. 検索条件と件数制限

- **検索条件未設定**：最新100件のみ表示（DB負荷軽減のため）
- **検索条件設定**：検索結果全件を取得（100件以上も表示可能）

---

## 日常的な起動・停止手順

### ✅ 起動手順（開発・テスト開始時）

#### Push通知使用時（推奨）

**ターミナル1（Django + MySQL）:**
```powershell
# 1. MySQLコンテナ起動
docker-compose up -d

# 2. 仮想環境アクティベート
.\venv\Scripts\Activate.ps1

# 3. Djangoサーバー起動
python manage.py runserver
```

**ターミナル2（ngrok）:**
```powershell
# プロジェクトフォルダに移動
cd "<プロジェクトフォルダ>/Car-Internal-System"

# ngrok起動
.\ngrok.exe http 8000
```

⚠️ **注意**: ngrok URLが変わった場合、Pub/Subサブスクリプションのエンドポイントを更新してください。

サーバーが起動したら **http://127.0.0.1:8000/sateiinfo/** にアクセス

#### 通常時（手動メール取得のみ）

```powershell
# 1. MySQLコンテナ起動
docker-compose up -d

# 2. 仮想環境アクティベート
.\venv\Scripts\Activate.ps1

# 3. Djangoサーバー起動
python manage.py runserver
```

サーバーが起動したら **http://127.0.0.1:8000/sateiinfo/** にアクセス

---

### ⛔ 停止手順（開発・テスト終了時）

#### Push通知使用時（ngrok起動中）

```powershell
# 1. ngrok停止
# → ngrokを起動しているターミナルで Ctrl + C を押す

# 2. Djangoサーバー停止
# → Djangoを起動しているターミナルで Ctrl + C または Ctrl + Break を押す

# 3. MySQLコンテナ停止
docker-compose stop

# 4. 仮想環境を抜ける（任意）
deactivate
```

#### 通常時（ngrok未使用）

```powershell
# 1. Djangoサーバー停止
# → ターミナルで Ctrl + C を押す

# 2. MySQLコンテナ停止
docker-compose stop

# 3. 仮想環境を抜ける（任意）
deactivate
```

---

### 💡 開発のベストプラクティス

#### 推奨フロー

**朝一の起動**
```powershell
docker-compose up -d              # MySQL起動
.\venv\Scripts\Activate.ps1       # 仮想環境
python manage.py runserver        # サーバー起動
```

**作業中**
- Djangoサーバーは起動したまま
- MySQLも起動したまま
- コード変更は自動反映される（再起動不要）

**終業時の停止**
```powershell
Ctrl + C                          # サーバー停止
docker-compose stop               # MySQL停止
deactivate                        # 仮想環境を抜ける
```

---

### 🔄 よく使うコマンド

#### MySQLの状態確認
```powershell
# コンテナが起動しているか確認
docker-compose ps

# ログを確認
docker-compose logs mysql
```

#### MySQLの完全停止（ボリューム削除）
```powershell
# データも含めて完全削除（注意！）
docker-compose down -v
```

#### 新しいメール取得
```powershell
# サーバー起動中でも実行可能（別のターミナルで）
python manage.py fetch_gmail
```

---

### ⚠️ 注意点

#### MySQLは起動したまま放置してもOK
- リソース消費は少ない
- 毎回停止する必要はありません
- PCを再起動しても自動起動しません（手動で `docker-compose up -d`）

#### Djangoサーバーは作業中だけ起動
- 開発中のみ起動
- コード変更時は自動でリロードされる
- エラーが出たら Ctrl+C で停止して再起動

#### データベースのバックアップ（重要データの場合）
```powershell
# データベースをエクスポート
docker exec navikuru-mysql mysqldump -u navikuru_user -pnavikuru_pass navikuru_db > backup.sql

# インポート
docker exec -i navikuru-mysql mysql -u navikuru_user -pnavikuru_pass navikuru_db < backup.sql
```

---

### 🛠️ トラブルシューティング

#### ポートが使用中の場合
```powershell
# 8000番ポートを使用しているプロセスを探す
netstat -ano | findstr :8000

# プロセスを終了（PIDを確認してから）
taskkill /PID <PID番号> /F
```

#### MySQLに接続できない場合
```powershell
# コンテナの状態確認
docker-compose ps

# ログ確認
docker-compose logs mysql

# 再起動
docker-compose restart mysql
```

---

## Gmail API設定（次のステップ）

### 📋 やること（OAuth 2.0方式 - 推奨）
1. **GCPプロジェクト作成 & Gmail API有効化**
2. **OAuth 2.0クライアントID作成**
3. **`credentials.json` をダウンロードしてプロジェクトルートに配置**
4. **認証テスト実行（初回のみブラウザで認証）**

### 📖 詳細手順
**[OAUTH_SETUP.md](OAUTH_SETUP.md)** を参照してください。

### 🔄 DWD（ドメインワイド委任）方式への切り替え
後でDWD方式に切り替えたい場合は、**[GMAIL_API_SETUP.md](GMAIL_API_SETUP.md)** を参照してください。

---

## Gmail API接続テスト（OAuth 2.0認証）

```powershell
python test_oauth.py
```

初回実行時はブラウザが開きます。Googleアカウントでログインして認証してください。

成功すると以下のように表示されます:
```
====================================================================
✅ 接続成功！
====================================================================
メールアドレス: receiver@example.com
総メール数: 1,234
====================================================================
```

---

## Gmail Push通知設定（推奨：コスト削減）

### 🔔 Push通知とは？

従来の定期ポーリングではなく、Gmailから**新着メールがあるときだけ**通知を受け取る仕組みです。

**メリット:**
- ⚡ **リアルタイム**: 新着メール到着後、数秒以内に検知
- 💰 **コスト削減**: APIコールが約93%削減（1日1,440回 → 100回程度）
- 📉 **サーバー負荷軽減**: 常時ポーリング不要

**仕組み:**
```
新着メール → Gmail → Pub/Sub → Webhook → Django → メール取得・DB保存
```

### 📋 セットアップ手順

詳細は **[GMAIL_PUSH_SETUP.md](GMAIL_PUSH_SETUP.md)** を参照してください。

**クイックスタート:**

1. **依存パッケージインストール**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Google Cloud Pub/Subトピック作成**（初回のみ）
   - Google Cloud Console → Pub/Sub → トピック作成
   - トピック名: `gmail-push`

3. **ngrok起動**（ローカル開発時）
   ```powershell
   ngrok http 8000
   ```

4. **Gmail Watch設定**
   ```powershell
   python manage.py gmail_watch_start --topic projects/YOUR-PROJECT-ID/topics/gmail-push
   ```

5. **動作確認**
   - テストメールを送信
   - WEB画面で新規申込を確認

⚠️ **注意**: Watch設定は7日間で自動的に無効になります。定期的に再設定してください。

---

## メール取得実行（手動・バックアップ用）

Push通知を設定した場合でも、手動でメール取得することができます。

```
## メール取得実行

```powershell
# デフォルト（1日以内のメールを最大67100件取得して自動パース）
# ※取得後はWEB画面（http://127.0.0.1:8000/sateiinfo/）で確認できます
python manage.py fetch_gmail

# オプション指定
python manage.py fetch_gmail --days 3 --max 200
```

**実行結果例**:
```
============================================================
Gmail メール取得開始
============================================================

✓ Gmail API接続成功（system@gigicompany.jp）

検索条件: subject:申込み依頼がございました from:sender@example.com to:receiver@example.com newer_than:1d
最大取得件数: 100
取得: 最新3件（新しい順）

3件のメールが見つかりました

  [1/3] ✓ 新規保存 & 申込情報抽出 【かんたん車査定ガイド】申込み依頼がございました。
  [2/3] ✓ 新規保存 & 申込情報抽出 【かんたん車査定ガイド】申込み依頼がございました。
  [3/3] - スキップ（既存）

============================================================
✅ 完了
  新規保存: 2件
  申込情報抽出: 2件
  スキップ: 1件
============================================================
```

### 常駐運用（1分ごと実行）
定期実行（cron / タスクスケジューラ）で以下を実行:
```powershell
# 1分ごとに実行
python manage.py fetch_gmail
```
→ 新着メールのみ取得・処理（既存は自動スキップ）

**見逃し防止の仕組み**:
- ✅ Gmail APIは**新しいメールから順**に返します
- ✅ 最大100件取得 = 1日で100件まで対応
- ✅ 1分ごと実行なら、1分間に100件以上来ることはまずないので**見逃しゼロ**
- ✅ もし大量に来る場合は `--max 500` などで増やせます

### 重複防止の仕組み（完全保証）

**2段階チェック**で同じメール・同じ申込を絶対に重複登録しません：

1. **第1段階: メールレベルの重複防止**
   - `GmailMessage.message_id` に **UNIQUE制約**
   - Gmail APIの固有ID（例: `18d1a2b3c4d5e6f7`）で判定
   - → 同じメールは1回しか保存されない

2. **第2段階: 申込番号レベルの重複防止**
   - `CarAssessmentRequest.application_number` に **UNIQUE制約**
   - お申込番号（例: `9060727`）で判定
   - → 同じ申込番号は1回しか保存されない

**動作例**:
```python
# 1回目の実行
→ メール3件取得 → すべて新規保存（3件）

# 2回目の実行（1分後）
→ メール3件取得 → すべて既存（スキップ、0件）

# 3回目の実行（新着1件あり）
→ メール4件取得 → 新規1件、既存3件スキップ（1件）
```

何回実行しても **安全** です！

### 取得される情報
メール本文から以下の情報を自動抽出してDB保存:
- お申込番号（一意制約）
- お申込日時
- 希望売却時期
- メーカー名、車種名、年式、走行距離
- お名前、電話番号、郵便番号、住所、メールアドレス

---

## プロジェクト構成

```
.
├── config/                    # Django設定
│   ├── settings.py           # MySQL接続、環境変数対応済み
│   ├── urls.py
│   └── wsgi.py
├── ingest/                    # メール取込アプリ
│   ├── models.py             # GmailMessage & CarAssessmentRequest
│   ├── admin.py              # 管理画面設定
│   └── management/
│       └── commands/
│           └── fetch_gmail.py # メール取得 & 本文パース
├── docker-compose.yml         # MySQL (Docker)
├── .env                       # 環境変数
├── requirements.txt           # Python依存パッケージ
├── test_gmail_api.py          # Gmail API接続テスト
├── test_parse_body.py         # 本文パース機能テスト
├── GMAIL_API_SETUP.md         # Gmail API設定手順書
└── README.md                  # このファイル
```

---

## データベーススキーマ

### `gmail_messages` テーブル
| カラム名 | 型 | 説明 | 備考 |
|---------|-----|------|------|
| message_id | VARCHAR(255) | GmailメッセージID | **UNIQUE** |
| thread_id | VARCHAR(255) | スレッドID | |
| from_address | VARCHAR(255) | 送信元 | |
| to_address | VARCHAR(255) | 宛先 | |
| subject | VARCHAR(500) | 件名 | |
| received_at | DATETIME | 受信日時 | インデックス |
| created_at | DATETIME | 取り込み日時 | 自動設定 |
| snippet | TEXT | スニペット | |
| body_text | TEXT | 本文（テキスト） | **パース対象** |
| body_html | TEXT | 本文（HTML） | |
| raw_json | JSON | Gmail APIレスポンス | トラブルシュート用 |

**重複防止**: `message_id` に UNIQUE制約

### `car_assessment_requests` テーブル（新規）
| カラム名 | 型 | 説明 | 備考 |
|---------|-----|------|------|
| application_number | VARCHAR(50) | お申込番号 | **UNIQUE** |
| application_datetime | DATETIME | お申込日時 | インデックス |
| desired_sale_timing | VARCHAR(100) | 希望売却時期 | |
| maker | VARCHAR(100) | メーカー名 | |
| car_model | VARCHAR(100) | 車種名 | |
| year | VARCHAR(100) | 年式 | |
| mileage | VARCHAR(100) | 走行距離 | |
| customer_name | VARCHAR(100) | お名前 | インデックス |
| phone_number | VARCHAR(20) | 電話番号 | インデックス |
| postal_code | VARCHAR(10) | 郵便番号 | |
| address | VARCHAR(255) | 住所 | |
| email | VARCHAR(255) | メールアドレス | |
| gmail_message | FK | 元メッセージ（参照用） | |
| created_at | DATETIME | 取り込み日時 | 自動設定 |
| updated_at | DATETIME | 更新日時 | 自動更新 |

**重複防止**: `application_number` に UNIQUE制約  
**リレーション**: gmail_message → GmailMessage（外部キー）

---

## 管理画面でデータを参照する

### 1. 開発サーバーを起動

```powershell
python manage.py runserver
```

サーバーが起動したら、以下のメッセージが表示されます：
```
Starting development server at http://127.0.0.1:8000/
```

### 2. 管理画面にアクセス

ブラウザで以下のURLを開きます：

**http://127.0.0.1:8000/admin/**

### 3. ログイン

以下の認証情報でログインします：

| 項目 | 値 |
|------|-----|
| **ユーザー名** | `system` |
| **メールアドレス** | `system@gigcompany.jp` |
| **パスワード** | `#1Qazxsw2` |

⚠️ **本番環境では必ずパスワードを変更してください**

### 4. データを確認

ログイン後、以下の2つのテーブルが表示されます：

#### 📧 Gmail messages（Gmailメッセージ）
取得したメールの生データを確認できます。

**確認できる情報：**
- Message ID（Gmail固有ID）
- From（送信元）
- To（宛先）
- Subject（件名）
- Received at（受信日時）
- Body text（本文）
- Raw JSON（Gmail APIの生レスポンス）

**操作：**
1. 「Gmail messages」をクリック
2. メール一覧が表示されます
3. 任意のメールをクリックすると詳細が表示されます
4. 検索ボックスで件名や送信元を検索できます
5. 右側のフィルタで受信日時で絞り込みできます

#### 🚗 Car assessment requests（車査定申込）
メール本文からパースした申込情報を確認できます。

**確認できる情報：**
- お申込番号（一意）
- お申込日時
- 希望売却時期
- メーカー名、車種名、年式、走行距離
- お名前、電話番号、郵便番号、住所、メールアドレス
- Gmail message（元メールへのリンク）

**操作：**
1. 「Car assessment requests」をクリック
2. 申込情報一覧が表示されます
3. 任意の申込をクリックすると詳細が表示されます
4. 検索ボックスでお申込番号、お名前、電話番号を検索できます
5. 右側のフィルタでメーカーや申込日時で絞り込みできます
6. 「Gmail message」リンクをクリックすると元のメールを確認できます

### 5. データのエクスポート

一覧画面で以下の操作でデータをエクスポートできます：

1. エクスポートしたいデータにチェックを入れる（全件選択も可能）
2. 画面上部の「アクション」ドロップダウンから選択
3. 「実行」ボタンをクリック

---

## 管理画面の詳細機能

### 検索機能
- **Gmail messages**: 件名、送信元、宛先、Message IDで検索
- **Car assessment requests**: お申込番号、お名前、電話番号、メールアドレスで検索

### フィルタ機能
- **Gmail messages**: 受信日時（今日、過去7日間、今月、今年）
- **Car assessment requests**: 
  - メーカー（トヨタ、日産、ホンダなど）
  - 申込日時（今日、過去7日間、今月、今年）

### ソート機能
- 各列のヘッダーをクリックすると昇順・降順で並び替えできます

### ページング
- 100件ごとにページング（設定変更可能）

---

## 管理コマンド一覧

### メール取得
```powershell
# 手動でメール取得（1日以内、最大100件）
python manage.py fetch_gmail

# オプション指定
python manage.py fetch_gmail --days 7 --max 500

# 障害時の手動範囲回収（from/to 指定）
# 例: 09:00〜12:00 の範囲を回収
python manage.py fetch_gmail --from "2026-02-16 09:00" --to "2026-02-16 12:00" --max 500

# 日付のみ指定も可（to は翌日 00:00 扱い）
python manage.py fetch_gmail --from "2026-02-16" --to "2026-02-17" --max 500
```

### Gmail Push通知管理

#### Watch設定開始
```powershell
python manage.py gmail_watch_start --topic projects/YOUR-PROJECT-ID/topics/gmail-push
```

**オプション:**
- `--topic`: Pub/Subトピック名（必須）
- `--label`: 監視するラベル（デフォルト: INBOX）

**実行例:**
```powershell
python manage.py gmail_watch_start --topic projects/my-project-123/topics/gmail-push --label INBOX
```

#### Watch設定停止
```powershell
python manage.py gmail_watch_stop
```

⚠️ **重要**: Watch設定は7日間で自動的に無効になるため、定期的に再実行してください。

---

## よくある質問

### Q: 管理画面のパスワードを変更したい
```powershell
python manage.py changepassword system
```
新しいパスワードを2回入力してください。

### Q: 管理画面のパスワードを忘れた
```powershell
# パスワードをリセット
python manage.py changepassword system
```

### Q: MySQLを再起動したい
```powershell
docker-compose restart
```

### Q: MySQLを停止したい
```powershell
docker-compose down
```

### Q: データベースをリセットしたい
```powershell
docker-compose down -v  # ボリュームごと削除
docker-compose up -d
python manage.py migrate
python manage.py createsuperuser --username system --email system@gigcompany.jp
```
パスワードを入力してください。

### Q: Gmail APIで403エラーが出る
→ [GMAIL_API_SETUP.md](GMAIL_API_SETUP.md) のトラブルシューティングを確認

---

## 今後の拡張

- [ ] メール本文の取得（現在はスニペットのみ）
- [ ] 添付ファイルの取得
- [ ] 既読化・ラベル付け（`gmail.modify` スコープ追加）
- [ ] 定期実行（cron / Cloud Scheduler）
- [ ] Cloud SQLへの移行
- [ ] GCE / Cloud Run へのデプロイ

---

## 本番環境への移行（参考）

### クエリ性能確認（推奨）
- Cloud SQL 本番投入前に実施: [CLOUDSQL_EXPLAIN_RUNBOOK.md](CLOUDSQL_EXPLAIN_RUNBOOK.md)

### Cloud SQL（MySQL）
1. Cloud SQLインスタンス作成
2. `.env` の DB接続情報を更新
3. Cloud SQL Auth Proxy で接続

### デプロイ
- GCE（Compute Engine）
- Cloud Run
- App Engine

詳細は別途ドキュメント化予定

---

## ライセンス
社内利用のみ

