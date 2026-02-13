# Gmail API 環境設定手順（ドメインワイド委任）

このドキュメントはGmail APIをドメインワイド委任（DWD）で使用するための設定手順です。

## 前提条件
- Google Workspace（旧 G Suite）アカウント
- Workspace管理者権限
- GCPプロジェクト作成権限

---

## 手順1: GCPプロジェクト作成とAPI有効化

### 1-1. GCPプロジェクト作成
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを新規作成（例: `navikuru-mail-system`）

### 1-2. Gmail API有効化
1. 左メニュー「APIとサービス」→「ライブラリ」
2. 「Gmail API」を検索
3. 「有効にする」をクリック

---

## 手順2: サービスアカウント作成

### 2-1. サービスアカウント作成
1. 「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「サービスアカウント」
3. サービスアカウント名: `navikuru-gmail-reader`（任意）
4. 「作成して続行」→ ロールは不要（スキップ）→「完了」

### 2-2. ドメインワイド委任を有効化

**最新のUI（2026年版）**:

1. 作成したサービスアカウントをクリック
2. 上部の「詳細設定を表示」を展開（または自動的に表示されている場合あり）
3. **「ドメイン全体の委任」** セクションを探す
4. 「ドメイン全体の委任を有効にする」をクリック
   - または、既に「⚠️ 警告メッセージ」が表示されている場合は既に有効化されています
5. 「保存」をクリック

**別の方法（もし上記が見つからない場合）**:
1. サービスアカウント一覧画面で、作成したアカウントの行を探す
2. 右側の「...」（その他のアクション）→ 「詳細を編集」
3. 「ドメイン全体の委任を有効にする」のチェックボックスをオンにする
4. 「保存」

**確認方法**: 
- サービスアカウント詳細画面の「ドメイン全体の委任」セクションに警告メッセージが表示されていればOK
- Client ID（数字の文字列）が表示されていることを確認

### 2-3. Client IDをメモ

ドメインワイド委任を有効化すると、「ドメイン全体の委任」セクションに以下が表示されます：

- **クライアントID**（または「OAuth 2 クライアント ID」）: 数字の文字列
- 例: `118254875517875769356`

118254875517875769356

**このClient IDをコピーしてメモしてください** → 手順3で使用します

**見つからない場合**:
- サービスアカウントの「詳細」タブを確認
- 「一意のID」という項目があればそれがClient IDです

### 2-4. JSONキーを発行
1. 「キー」タブを開く
2. 「鍵を追加」→「新しい鍵を作成」
3. キーのタイプ: **JSON**
4. 「作成」→ JSONファイルがダウンロードされる
5. **このファイルをプロジェクトルートに `credentials.json` として保存**

⚠️ **重要**: このJSONファイルは秘密鍵です。Gitにコミットしないでください！

---

## 手順3: Workspace管理コンソールでドメインワイド委任を許可

### 3-1. Workspace管理コンソールにアクセス
1. [Google Workspace管理コンソール](https://admin.google.com/)にアクセス
2. 管理者アカウントでログイン

### 3-2. APIコントロール設定

**最新のUI（2026年版）では複数のパターンがあります**:

#### パターン1: セキュリティ直下にある場合
1. 左メニュー「セキュリティ」をクリック
2. **「APIの制御」** を直接クリック
3. 「ドメイン全体の委任」タブを選択
4. 「新しく追加」または「新規追加」をクリック

#### パターン2: アクセスとデータの制御にある場合
1. 左メニュー「セキュリティ」→「アクセスとデータの制御」
2. 「APIの制御」をクリック
3. 「ドメイン全体の委任」タブを選択
4. 「新しく追加」をクリック

#### パターン3: 検索機能を使う（最も確実）
1. 管理コンソール上部の**検索ボックス**に「ドメイン全体の委任」と入力
2. 検索結果から「ドメイン全体の委任」を選択
3. 「新しく追加」または「新規追加」をクリック

**どのパターンでも最終的に同じ画面に到達します**

### 3-3. クライアントIDとスコープを登録
**クライアントID**: （手順2-3でメモしたClient ID）
```
123456789012345678901
```

**OAuth スコープ**:（最初は読み取り専用でOK）
```
https://www.googleapis.com/auth/gmail.readonly
```

※将来的に既読化やラベル付けをする場合は以下も追加:
```
https://www.googleapis.com/auth/gmail.modify
```

4. 「承認」をクリック

---

## 手順4: .envファイル設定

プロジェクトルートの `.env` ファイルを編集:

```bash
# Gmail API設定
GMAIL_SERVICE_ACCOUNT_FILE=credentials.json
GMAIL_DELEGATED_EMAIL=system@gigicompany.jp
```

---

## 手順5: 接続テスト

### 5-1. テストスクリプト実行
```powershell
python test_gmail_api.py
```

### 5-2. 成功例
```
============================================================
Gmail API 接続テスト（DWD）
============================================================

✓ サービスアカウントファイル: credentials.json
✓ 委任先メールアドレス: system@gigicompany.jp
✓ Gmail APIサービス構築完了

--- メール検索テスト ---
検索条件: from:info@a-satei.com to:kaitori@gigicompany.jp newer_than:7d

✅ メール取得成功！ 3件

  [1] メッセージID: 1234567890abcdef
      From: info@a-satei.com
      To: kaitori@gigicompany.jp
      Subject: 【ナビクル】新着査定依頼
      Date: Thu, 6 Feb 2026 10:00:00 +0900

============================================================
✅ Gmail API接続テスト成功！
============================================================
```

---

## トラブルシューティング

### エラー: `Service account does not have domain-wide delegation enabled`
→ 手順2-2でドメインワイド委任を有効化していない

### エラー: `Not authorized to access this resource/api`
→ 手順3でWorkspace管理コンソールの設定が完了していない
→ Client IDとスコープが正しく登録されているか確認

### エラー: `Invalid grant`
→ GMAIL_DELEGATED_EMAILのメールアドレスが間違っている
→ または、該当メールアドレスがWorkspaceドメイン内に存在しない

### メールが取得できない
→ system@gigicompany.jp に実際にメールが届いているか確認
→ 検索条件（from/to/newer_than）が正しいか確認

---

## 次のステップ

接続テストが成功したら:

```powershell
# Djangoサーバー起動
python manage.py runserver

# 別のターミナルでメール取得実行
python manage.py fetch_gmail

# 管理画面で確認
# http://127.0.0.1:8000/admin/
# ユーザー名: admin
# パスワード: （createsuperuserで設定したパス）
```

---

## セキュリティ注意事項

1. **credentials.json は絶対にGitにコミットしない**
   - `.gitignore` に `*.json` を追加済み
   
2. **本番環境ではSecret Managerを使用**
   - GCP Secret Managerや環境変数で管理
   
3. **最小権限の原則**
   - 最初は `gmail.readonly` のみ
   - 必要に応じて `gmail.modify` を追加

---

## 参考リンク

- [Using OAuth 2.0 for Server to Server Applications](https://developers.google.com/identity/protocols/oauth2/service-account)
- [Control API access with domain-wide delegation](https://support.google.com/a/answer/162106)
- [Gmail API Reference](https://developers.google.com/gmail/api/reference/rest)
