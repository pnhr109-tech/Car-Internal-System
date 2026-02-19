import os

from django.core.management.base import BaseCommand
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/chat.spaces.readonly',
    'https://www.googleapis.com/auth/chat.messages.readonly',
]


class Command(BaseCommand):
    help = 'トップページ表示用に Gmail/Calendar/Chat の read 権限付き token.json を生成します。'

    def handle(self, *args, **options):
        credentials_file = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')
        token_file = os.getenv('GMAIL_TOKEN_FILE', 'token.json')

        if not os.path.exists(credentials_file):
            self.stdout.write(self.style.ERROR(f'credentials.json が見つかりません: {credentials_file}'))
            return

        self.stdout.write('Google OAuth認証を開始します。ブラウザで承認してください。')

        try:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        except Exception as error:
            self.stdout.write(self.style.ERROR(f'認証に失敗しました: {error}'))
            return

        with open(token_file, 'w', encoding='utf-8') as token_handle:
            token_handle.write(creds.to_json())

        self.stdout.write(self.style.SUCCESS(f'token.json を更新しました: {token_file}'))
        self.stdout.write('取得済みスコープ:')
        for scope in SCOPES:
            self.stdout.write(f'  - {scope}')