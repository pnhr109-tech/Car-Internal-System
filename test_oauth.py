"""
OAuth 2.0認証テスト
初回実行時にブラウザが開いてGoogleアカウント認証を行います。
"""
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# スコープ設定
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def test_oauth():
    """OAuth 2.0認証をテストしてGmail APIに接続"""
    print("=" * 60)
    print("OAuth 2.0 認証テスト")
    print("=" * 60)
    
    credentials_file = 'credentials.json'
    token_file = 'token.json'
    
    # credentials.jsonの存在確認
    if not os.path.exists(credentials_file):
        print(f"\n❌ エラー: {credentials_file} が見つかりません")
        print("\n【対処方法】")
        print("1. Google Cloud ConsoleでOAuth 2.0クライアントIDを作成")
        print("2. credentials.jsonをダウンロードしてこのフォルダに配置")
        print("3. 詳細は OAUTH_SETUP.md を参照")
        return
    
    creds = None
    
    # token.jsonが存在する場合は読み込む
    if os.path.exists(token_file):
        print(f"\n✓ {token_file} を読み込み中...")
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            print("✓ トークン読み込み成功")
        except Exception as e:
            print(f"⚠ token.json読み込み失敗: {e}")
            creds = None
    
    # 認証が必要な場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # トークンをリフレッシュ
            print("\n🔄 アクセストークンを更新中...")
            try:
                creds.refresh(Request())
                print("✓ トークン更新成功")
            except Exception as e:
                print(f"❌ トークン更新失敗: {e}")
                creds = None
        
        # 新規認証が必要
        if not creds:
            print("\n" + "=" * 60)
            print("🔐 初回認証が必要です")
            print("=" * 60)
            print("ブラウザが開きます。Googleアカウントでログインしてください。")
            print("認証後、このウィンドウに戻ります。")
            print("")
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
                print("\n✓ 認証成功")
            except Exception as e:
                print(f"\n❌ 認証失敗: {e}")
                return
        
        # token.jsonに保存
        try:
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
            print(f"✓ 認証情報を保存: {token_file}")
        except Exception as e:
            print(f"⚠ token.json保存失敗: {e}")
    
    # Gmail APIサービス構築
    print("\n🔧 Gmail APIサービスを構築中...")
    try:
        service = build('gmail', 'v1', credentials=creds)
        print("✓ Gmail API接続成功")
    except Exception as e:
        print(f"❌ Gmail API接続失敗: {e}")
        return
    
    # 接続テスト: プロフィール情報を取得
    print("\n📧 Gmail接続テスト中...")
    try:
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'N/A')
        total_messages = profile.get('messagesTotal', 0)
        
        print("\n" + "=" * 60)
        print("✅ 接続成功！")
        print("=" * 60)
        print(f"メールアドレス: {email}")
        print(f"総メール数: {total_messages:,}")
        print("=" * 60)
        
        # 最新メール1件を取得してテスト
        print("\n📬 最新メール1件を取得中...")
        results = service.users().messages().list(
            userId='me',
            maxResults=1
        ).execute()
        
        messages = results.get('messages', [])
        if messages:
            msg = messages[0]
            detail = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            
            headers = {h['name']: h['value'] for h in detail.get('payload', {}).get('headers', [])}
            
            print("\n最新メール:")
            print(f"  From: {headers.get('From', 'N/A')}")
            print(f"  Subject: {headers.get('Subject', 'N/A')}")
            print(f"  Date: {headers.get('Date', 'N/A')}")
        else:
            print("メールボックスにメールがありません")
        
        print("\n" + "=" * 60)
        print("✅ OAuth 2.0認証テスト完了")
        print("=" * 60)
        print("\n次のステップ:")
        print("  python manage.py fetch_gmail --days 1 --max 10")
        print("")
        
    except Exception as e:
        print(f"\n❌ Gmail接続テスト失敗: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_oauth()
