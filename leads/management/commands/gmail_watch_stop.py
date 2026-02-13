"""
Gmail Push通知（Watch）を停止する管理コマンド
"""
from django.core.management.base import BaseCommand
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os


class Command(BaseCommand):
    help = 'Gmail Push通知（Watch）を停止します'

    def handle(self, *args, **options):
        self.stdout.write('=' * 60)
        self.stdout.write('Gmail Push通知（Watch）停止')
        self.stdout.write('=' * 60)
        
        try:
            # Gmail APIサービスを構築
            service = self._build_gmail_service()
            
            # Watch を停止
            service.users().stop(userId='me').execute()
            
            self.stdout.write(self.style.SUCCESS('\n✅ Watch設定を停止しました'))
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
