"""
Gmail Push通知（Watch）を開始する管理コマンド
"""
from django.core.management.base import BaseCommand
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import pickle


class Command(BaseCommand):
    help = 'Gmail Push通知（Watch）を開始します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--topic',
            type=str,
            required=True,
            help='Pub/Subトピック名（例: projects/your-project/topics/gmail-push）'
        )
        parser.add_argument(
            '--label',
            type=str,
            default='INBOX',
            help='監視するラベル（デフォルト: INBOX）'
        )

    def handle(self, *args, **options):
        topic_name = options['topic']
        label = options['label']
        
        self.stdout.write('=' * 60)
        self.stdout.write('Gmail Push通知（Watch）設定開始')
        self.stdout.write('=' * 60)
        
        try:
            # Gmail APIサービスを構築
            service = self._build_gmail_service()
            
            # Watch リクエストを送信
            request = {
                'labelIds': [label],
                'topicName': topic_name
            }
            
            self.stdout.write(f'\n設定内容:')
            self.stdout.write(f'  トピック: {topic_name}')
            self.stdout.write(f'  ラベル: {label}')
            
            result = service.users().watch(userId='me', body=request).execute()
            
            self.stdout.write(self.style.SUCCESS('\n✅ Watch設定が完了しました！'))
            self.stdout.write(f'\n詳細:')
            self.stdout.write(f'  履歴ID: {result.get("historyId")}')
            self.stdout.write(f'  有効期限: {result.get("expiration")} (Unix timestamp)')
            
            # 有効期限を人間が読める形式に変換
            expiration = int(result.get('expiration', 0))
            if expiration:
                from datetime import datetime
                expiration_dt = datetime.fromtimestamp(expiration / 1000)
                self.stdout.write(f'  有効期限: {expiration_dt.strftime("%Y-%m-%d %H:%M:%S")}')
                self.stdout.write(f'\n⚠️  7日後に自動的に無効になります。定期的に再設定してください。')
            
            self.stdout.write('=' * 60)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ エラー: {str(e)}'))
            raise

    def _build_gmail_service(self):
        """Gmail APIサービスを構築"""
        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        creds = None
        
        # token.jsonからクレデンシャルを読み込み
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # クレデンシャルが無効または存在しない場合は再認証
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # token.jsonに保存
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        return build('gmail', 'v1', credentials=creds)
