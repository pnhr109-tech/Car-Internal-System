# Gmail Push通知（Pub/Sub）設定手順

Gmail APIのPush通知を使用して、新着メールを自動的に検知してデータベースに保存します。

## 📋 概要

従来の定期ポーリング方式ではなく、Gmail Push通知を使用することでコストを削減します。

**仕組み:**
```
新着メール → Gmail → Pub/Sub → Webhook → Django → メール取得・DB保存
```

**メリット:**
- ⚡ リアルタイム検知（数秒以内）
- 💰 APIコール削減（定期ポーリング不要）
- 📉 コスト削減

---

## 🔧 事前準備

### 1. Google Cloud Consoleでの設定

#### Step 1: Pub/Subトピック作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 既存のプロジェクトを選択（Gmail API有効化済みのプロジェクト）
3. 左メニュー → **Pub/Sub** → **トピック** を選択
4. **トピックを作成** をクリック
5. 以下を入力：
   - **トピックID**: `gmail-push`（任意の名前）
   - その他はデフォルトのまま
6. **作成** をクリック
7. 作成されたトピック名をコピー（例: `projects/your-project-id/topics/gmail-push`）

#### Step 2: Pub/Subトピックに権限を追加

Gmail APIがPub/Subトピックにメッセージを送信できるように権限を設定します。

1. 作成したトピック `gmail-push` をクリック
2. 上部のタブから **権限** を選択
3. **プリンシパルを追加** ボタンをクリック
4. 以下を入力：
   - **新しいプリンシパル**: `gmail-api-push@system.gserviceaccount.com`
   - **ロールを選択**: `Pub/Sub パブリッシャー` を検索して選択
5. **保存** をクリック

⚠️ **重要**: この権限設定がないと、`gmail_watch_start`コマンド実行時に403エラーが発生します。

---

### 2. ローカル開発環境でのセットアップ（ngrok使用）

#### Step 1: ngrokのインストール

**① ngrokをダウンロード**

1. [ngrok公式サイト](https://ngrok.com/) にアクセス
2. **Sign up for free** でアカウント登録（無料）
3. ログイン後、ダッシュボードから **Windows (64-bit)** をダウンロード
4. ダウンロードした `ngrok.zip` を解凍
5. 解凍した `ngrok.exe` をプロジェクトフォルダにコピー


**② 認証トークンを設定**

ngrokダッシュボードから認証トークンをコピー（例: `<YOUR_NGROK_AUTHTOKEN>`）

PowerShellで以下を実行：

```powershell
# プロジェクトフォルダに移動
cd "C:\Users\pnhr1\OneDrive\ドキュメント\01_gigi_work\01_社内システム\01_アプリ開発\Car-Internal-System"

# 認証トークンを設定
.\ngrok.exe config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

成功すると以下のように表示されます：
```
Authtoken saved to configuration file: C:\Users\pnhr1\.ngrok2\ngrok.yml
```

**③ ngrokの動作確認**

```powershell
# ngrokのバージョン確認
.\ngrok.exe version
```

#### Step 2: 依存パッケージのインストール

```powershell
# 仮想環境をアクティベート
.\venv\Scripts\Activate.ps1

# パッケージをインストール
pip install -r requirements.txt
```

#### Step 3: Djangoサーバーを起動

**ターミナル1（Djangoサーバー用）**

```powershell
# プロジェクトフォルダに移動
cd "C:\Users\pnhr1\OneDrive\ドキュメント\01_gigi_work\01_社内システム\01_アプリ開発\Car-Internal-System"

# 仮想環境アクティベート
.\venv\Scripts\Activate.ps1

# MySQLコンテナ起動（まだの場合）
docker-compose up -d

# Djangoサーバー起動
python manage.py runserver
```

サーバーが起動したら、以下のように表示されます：
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

**ターミナル2（ngrok用）**

**新しいPowerShellウィンドウ**を開いて、以下を実行：

```powershell
# プロジェクトフォルダに移動
cd "C:\Users\pnhr1\OneDrive\ドキュメント\01_gigi_work\01_社内システム\01_アプリ開発\Car-Internal-System"

# ngrok起動
.\ngrok.exe http 8000
```

ngrokが起動すると、以下のような画面が表示されます：

```
ngrok                                                                                                                                           

Session Status                online
Account                       your-email@example.com
Version                       3.x.x
Region                        Japan (jp)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://xxxx-xxxx-xxxx.ngrok-free.app -> http://localhost:8000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

**あなたのngrok URL:**
```
https://<YOUR-NGROK-DOMAIN>.ngrok-free.app
```

#### Step 4: Pub/Subサブスクリプション作成（Webhookエンドポイント登録）

**詳細な手順:**

1. [Google Cloud Console](https://console.cloud.google.com/) を開く
2. プロジェクト `navikuru-mail-system` を選択
3. 左メニュー → **Pub/Sub** → **サブスクリプション** をクリック
4. 上部の **サブスクリプションを作成** ボタンをクリック
5. 以下の項目を入力：

   **① サブスクリプション ID**
   ```
   gmail-push-subscription
   ```
   
   **② Cloud Pub/Sub トピックを選択**
   - 「トピックを選択」をクリック
   - `gmail-push` を選択
   
   **③ 配信タイプ**
   - **「プッシュ」** を選択（重要！）
   - ⚠️ ここで「プッシュ」を選択すると、下に新しいフィールドが表示されます
   
   **④ エンドポイント URL**（「プッシュ」選択後に表示されます）
   ```
   https://<YOUR-NGROK-DOMAIN>.ngrok-free.app/sateiinfo/webhook/gmail-push/
   ```
   
   **⑤ その他の設定**
   - 「サブスクリプションの有効期限」: デフォルト（期限なし）
   - 「確認応答の期限」: デフォルト（10秒）
   - 「メッセージ保持期間」: デフォルト（7日）
   - その他はすべてデフォルトのまま

6. 画面下部の **作成** ボタンをクリック

**確認:**
- サブスクリプション一覧に `gmail-push-subscription` が表示される
- 「配信タイプ: プッシュ」と表示される
- エンドポイントURLが正しく設定されている

⚠️ **重要**: 
- 配信タイプで「プッシュ」を選択しないと、エンドポイントURLの入力欄は表示されません
- ngrokを再起動してURLが変わった場合は、サブスクリプションを編集してURLを更新してください

---

### 3. Gmail Watchの開始

```powershell
# 仮想環境内で実行
python manage.py gmail_watch_start --topic projects/navikuru-mail-system/topics/gmail-push
```

**実行例:**
```
============================================================
Gmail Push通知（Watch）設定開始
============================================================

設定内容:
  トピック: projects/your-project-123/topics/gmail-push
  ラベル: INBOX

✅ Watch設定が完了しました！

詳細:
  履歴ID: 12345678
  有効期限: 2026-02-20 15:30:00

⚠️  7日後に自動的に無効になります。定期的に再設定してください。
============================================================
```

⚠️ **重要**: Watchは7日間で自動的に無効になります。定期的に再実行してください。

---

## 🧪 動作テスト

### テスト方法1: 手動テスト（Webhookエンドポイント確認）

**目的**: Pub/Subからのリクエストを受け取れるか確認

**前提条件**:
- ✅ Djangoサーバーが起動している (`python manage.py runserver`)
- ✅ ngrokが起動している (`.\ngrok.exe http 8000`)

**手順**:

1. **PowerShellで以下を実行**:
   ```powershell
   $ngrokUrl = "https://<YOUR-NGROK-DOMAIN>.ngrok-free.app"
   $body = @{ message = @{ data = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes('{"emailAddress":"kaitori@gigicompany.jp","historyId":"123"}')) } } | ConvertTo-Json
   
   Invoke-WebRequest -Uri "$ngrokUrl/sateiinfo/webhook/gmail-push/" -Method POST -Body $body -ContentType "application/json"
   ```

2. **期待される結果**:
   ```
   StatusCode        : 200
   StatusDescription : OK
   ```

3. **Djangoコンソールで確認すべきログ**:
   ```
   Received request body: b'{"message":{"data":"eyJlbWFpbEFkZHJlc3MiOiJrYWl0b3JpQGdpZ2ljb21wYW55LmpwIiwiaGlzdG9yeUlkIjoiMTIzIn0="}}'
   Parsed envelope: {'message': {'data': '...'}}
   Received push notification: {'emailAddress': 'kaitori@gigicompany.jp', 'historyId': '123'}
   Email: kaitori@gigicompany.jp, HistoryID: 123
   
   ============================================================
   Gmail メール取得開始
   ============================================================
   ✓ Gmail API接続成功
   
   検索条件: subject:申込み依頼がございました from:info@a-satei.com to:kaitori@gigicompany.jp newer_than:1d
   最大取得件数: 10
   取得: 最新10件（新しい順）
   
   X件のメールが見つかりました
   ...
   ✅ 完了
   [13/Feb/2026 13:XX:XX] "POST /sateiinfo/webhook/gmail-push/ HTTP/1.1" 200 0
   ```

4. **ngrokコンソールで確認**:
   ```
   POST /sateiinfo/webhook/gmail-push/ 200 OK
   ```

**❌ エラーが出る場合**:

- `400 Bad Request` → ALLOWED_HOSTSの設定を確認
- `Failed to fetch emails: No module named 'googleapiclient'` → Djangoサーバーを再起動
- `500 Internal Server Error` → Djangoコンソールのエラーログを確認

---

### テスト方法2: 実際のメールテスト（エンドツーエンド）

**目的**: Gmail新着 → Pub/Sub → ngrok → Django → DB保存の全体フローを確認

**前提条件**:
- ✅ Djangoサーバーが起動している
- ✅ ngrokが起動している
- ✅ Gmail Watch設定済み（有効期限内）
- ✅ Pub/Subサブスクリプション作成済み

**手順**:

1. **事前確認**: 現在の最新申込番号をメモ
   - http://127.0.0.1:8000/sateiinfo/ を開く
   - 一覧の一番上の申込番号を確認

2. **テストメールを送信**:
   - 送信元: `info@a-satei.com`
   - 送信先: `kaitori@gigicompany.jp`
   - 件名: `【かんたん車査定ガイド】申込み依頼がございました。`
   - 本文: 通常の申込メール内容

3. **Djangoコンソールを監視**（数秒～数十秒以内に自動的に動作）:
   ```
   Received request body: b'...'
   Parsed envelope: {'message': {'data': '...'}}
   Received push notification: {'emailAddress': 'kaitori@gigicompany.jp', 'historyId': 'XXXXXXX'}
   Email: kaitori@gigicompany.jp, HistoryID: XXXXXXX
   
   ============================================================
   Gmail メール取得開始
   ============================================================
   ✓ Gmail API接続成功
   
   1件のメールが見つかりました
     [1/1] ✓ 新規保存 & 申込情報抽出 【かんたん車査定ガイド】申込み依頼がございました。 [PC]
   
   ============================================================
   ✅ 完了
     新規保存: 1件
     申込情報抽出: 1件
     スキップ: 0件
   ============================================================
   [13/Feb/2026 13:XX:XX] "POST /sateiinfo/webhook/gmail-push/ HTTP/1.1" 200 0
   ```

4. **WEB画面で確認**:
   - http://127.0.0.1:8000/sateiinfo/ を開く（自動リロードされる）
   - 新規申込が一覧の一番上に表示される
   - 画面上部の通知ベル🔔に新着通知が表示される

5. **ngrokコンソールで確認**:
   ```
   HTTP Requests
   -------------
   13:XX:XX JST POST /sateiinfo/webhook/gmail-push/ 200 OK
   ```

**⏱️ タイミング**:
- メール送信から通知まで: 通常5～30秒
- Gmail側の処理遅延により、最大1～2分かかる場合もあります

**❌ 通知が来ない場合のチェックリスト**:

1. **Gmail Watch有効期限を確認**:
   - 2026-02-20 12:55:15より前か？
   - 期限切れの場合: `python manage.py gmail_watch_start --topic projects/navikuru-mail-system/topics/gmail-push`

2. **Pub/Subサブスクリプション確認**:
   - [Google Cloud Console](https://console.cloud.google.com/) → Pub/Sub → サブスクリプション
   - `gmail-push-subscription`が存在するか
   - 配信タイプが「プッシュ」になっているか
   - エンドポイントURLが正しいか（ngrokのURL）

3. **ngrokが起動しているか**:
   - ngrokコンソールに `Forwarding https://... -> http://localhost:8000` が表示されているか

4. **Djangoサーバーが起動しているか**:
   - http://127.0.0.1:8000/sateiinfo/ にアクセスできるか

5. **ngrok URLが変わっていないか**:
   - ngrokを再起動するとURLが変わります
   - 変わった場合: Pub/SubサブスクリプションのエンドポイントURLを更新

---

### テスト方法3: ログレベル確認

**Djangoコンソールで見るべきログ**:

✅ **正常な場合**:
```
Received request body: b'...'
Parsed envelope: {'message': {'data': '...'}}
Received push notification: {'emailAddress': 'kaitori@gigicompany.jp', 'historyId': '...'}
Email: kaitori@gigicompany.jp, HistoryID: ...
Email fetch triggered successfully
```

❌ **エラーがある場合**:
```
Failed to fetch emails: No module named 'googleapiclient'
→ 解決策: Djangoサーバーを再起動

JSON decode error: ...
→ 解決策: リクエストボディの形式を確認

Invalid HTTP_HOST header: '...'
→ 解決策: config/settings.pyのALLOWED_HOSTSを確認
```

---

### デバッグ用コマンド

**手動でメール取得（Push通知とは無関係）**:
```powershell
# 過去1日分を最大10件取得
python manage.py fetch_gmail --days 1 --max 10

# 過去7日分を全て取得
python manage.py fetch_gmail --days 7
```

**Gmail Watch状態確認**:
```powershell
# Watch設定停止（テスト用）
python manage.py gmail_watch_stop

# Watch設定再開（7日間有効）
python manage.py gmail_watch_start --topic projects/navikuru-mail-system/topics/gmail-push
```

**ngrok Web Interface**:
- http://127.0.0.1:4040 を開く
- リクエスト履歴、レスポンス詳細を確認できます

---

## 🚀 本番環境へのデプロイ

### Cloud Run / GCE / App Engine へのデプロイ

1. **アプリをデプロイ**
   - Cloud Run、GCE、App Engineなどにデプロイ
   - **公開URL**を取得（例: `https://your-app.run.app`）

2. **Pub/Subサブスクリプションを更新**
   - エンドポイントURL: `https://your-app.run.app/sateiinfo/webhook/gmail-push/`
   - ngrokではなく本番URLに変更

3. **Gmail Watchを再設定**
   ```bash
   python manage.py gmail_watch_start --topic projects/navikuru-mail-system/topics/gmail-push
   ```

4. **定期的なWatch更新（cron / Cloud Scheduler）**
   - 7日ごとにWatch設定を更新するジョブを設定
   ```bash
   # 例: Cloud Schedulerで毎週実行
   0 0 * * 0 python manage.py gmail_watch_start --topic projects/navikuru-mail-system/topics/gmail-push
   ```

---

## 🛠️ トラブルシューティング

### Webhookにリクエストが来ない

1. **Pub/Subサブスクリプションを確認**
   - エンドポイントURLが正しいか
   - ngrokが起動しているか
   - Djangoサーバーが起動しているか

2. **Gmail Watchが有効か確認**
   ```powershell
   # Watchの状態を確認（現在はコマンド未実装）
   # 7日経過していないか確認
   ```

3. **権限を確認**
   - Pub/Subトピックに `gmail-api-push@system.gserviceaccount.com` の権限があるか

### エラーログの確認

```powershell
# Djangoコンソールでエラーログを確認
# views.pyのloggerで出力されます
```

### Watch設定を停止

```powershell
python manage.py gmail_watch_stop
```

---

## 📊 コスト比較

### 従来の定期ポーリング方式
- 1分ごとに実行: **1,440回/日**
- 1ヶ月: **43,200回**
- Gmail API無料枠: **10億リクエスト/月**（十分）

### Push通知方式（推奨）
- 新着メールがあるときだけ実行
- 例: 100件/日の新着メール = **100回/日**
- 1ヶ月: **3,000回**
- **約93%削減！** 🎉

---

## 📝 日常運用

### ローカル開発時

1. MySQLコンテナ起動
   ```powershell
   docker-compose up -d
   ```

2. 仮想環境アクティベート
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

3. Djangoサーバー起動
   ```powershell
   python manage.py runserver
   ```

4. ngrok起動（別ターミナル）
   ```powershell
   ngrok http 8000
   ```

5. **初回のみ**: Gmail Watch設定
   ```powershell
   python manage.py gmail_watch_start --topic projects/navikuru-mail-system/topics/gmail-push
   ```

6. **ngrok URLが変わった場合**: Pub/Subサブスクリプションを更新

### 本番環境

- **7日ごとにWatch設定を更新**（Cloud Schedulerで自動化推奨）
- ログ監視

---

## 🔄 従来のポーリング方式との併用

Push通知とポーリングを併用することも可能です：

- **Push通知**: リアルタイム検知（メイン）
- **ポーリング**: バックアップ（1時間ごとなど）

```powershell
# 手動でポーリング（必要に応じて）
python manage.py fetch_gmail
```

---

## ⚠️ 注意事項

1. **Watch有効期限**: 7日間で自動的に無効になります
2. **ngrok無料版**: URLが毎回変わります（有料版は固定URL）
3. **Pub/Sub料金**: 無料枠あり（最初の10GBまで無料）
4. **セキュリティ**: 本番環境では適切な認証を実装してください

---

## 📚 参考リンク

- [Gmail API - Push Notifications](https://developers.google.com/gmail/api/guides/push)
- [Google Cloud Pub/Sub](https://cloud.google.com/pubsub/docs)
- [ngrok Documentation](https://ngrok.com/docs)
