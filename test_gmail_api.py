"""
Gmail API接続テストスクリプト
DWD（ドメインワイド委任）でsystem@gigicompany.jpのメールを取得できるか確認
"""
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# .env読み込み
load_dotenv()

# 設定
SERVICE_ACCOUNT_FILE = os.getenv('GMAIL_SERVICE_ACCOUNT_FILE', 'credentials.json')
DELEGATED_EMAIL = os.getenv('GMAIL_DELEGATED_EMAIL', 'system@gigicompany.jp')
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def test_gmail_api():
    """Gmail API接続テスト"""
    
    print("=" * 60)
    print("Gmail API 接続テスト（DWD）")
    print("=" * 60)
    
    # 1. サービスアカウントファイル確認
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"\n❌ エラー: サービスアカウントファイルが見つかりません")
        print(f"   ファイル: {SERVICE_ACCOUNT_FILE}")
        print(f"\n【次のステップ】")
        print(f"1. GCPでサービスアカウントのJSONキーを発行")
        print(f"2. プロジェクトルートに '{SERVICE_ACCOUNT_FILE}' として保存")
        print(f"3. .envファイルで GMAIL_SERVICE_ACCOUNT_FILE を設定")
        return False
    
    print(f"\n✓ サービスアカウントファイル: {SERVICE_ACCOUNT_FILE}")
    
    # 2. 認証情報作成（DWD）
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES
        )
        # ★DWDの核心：with_subject()で指定ユーザーになりすます
        delegated_credentials = credentials.with_subject(DELEGATED_EMAIL)
        print(f"✓ 委任先メールアドレス: {DELEGATED_EMAIL}")
        
    except Exception as e:
        print(f"\n❌ 認証情報の作成に失敗: {e}")
        return False
    
    # 3. Gmail API サービス構築
    try:
        service = build('gmail', 'v1', credentials=delegated_credentials)
        print(f"✓ Gmail APIサービス構築完了")
        
    except Exception as e:
        print(f"\n❌ Gmail APIサービス構築失敗: {e}")
        return False
    
    # 4. メール検索テスト
    print(f"\n--- メール検索テスト ---")
    query = 'subject:申込み依頼がございました from:info@a-satei.com to:kaitori@gigicompany.jp newer_than:1h'
    print(f"検索条件: {query}")
    
    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=5
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            print(f"\n⚠️  該当するメールが見つかりませんでした")
            print(f"   これは正常です（7日以内に該当メールがない場合）")
            print(f"\n【確認事項】")
            print(f"   - system@gigicompany.jpに実際にメールが届いているか")
            print(f"   - 検索条件が正しいか")
        else:
            print(f"\n✅ メール取得成功！ {len(messages)}件")
            
            for i, msg in enumerate(messages, 1):
                # 詳細取得
                detail = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in detail.get('payload', {}).get('headers', [])}
                
                print(f"\n  [{i}] メッセージID: {msg['id']}")
                print(f"      From: {headers.get('From', 'N/A')}")
                print(f"      To: {headers.get('To', 'N/A')}")
                print(f"      Subject: {headers.get('Subject', 'N/A')}")
                print(f"      Date: {headers.get('Date', 'N/A')}")
        
        print(f"\n" + "=" * 60)
        print(f"✅ Gmail API接続テスト成功！")
        print(f"=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ メール検索失敗: {e}")
        print(f"\n【考えられる原因】")
        print(f"1. Workspace管理コンソールでDWDが設定されていない")
        print(f"2. スコープが正しく登録されていない")
        print(f"   必要なスコープ: https://www.googleapis.com/auth/gmail.readonly")
        print(f"3. Gmail APIが有効化されていない")
        return False


if __name__ == '__main__':
    test_gmail_api()
