"""
Gmail メール取得 management command
使い方: python manage.py fetch_gmail
"""
import os
import re
import base64
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from leads.models import GmailMessage, CarAssessmentRequest


class Command(BaseCommand):
    help = 'Gmail APIからメールを取得してDBに保存'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='何日前までのメールを取得するか（デフォルト: 1日）'
        )
        parser.add_argument(
            '--max',
            type=int,
            default=100,
            help='最大取得件数（デフォルト: 100）※Gmail APIは新しい順に返すため見逃しなし'
        )

    def handle(self, *args, **options):
        days = options['days']
        max_results = options['max']
        
        self.stdout.write("=" * 60)
        self.stdout.write("Gmail メール取得開始")
        self.stdout.write("=" * 60)
        
        # 1. Gmail APIサービス構築
        service = self._build_gmail_service()
        if not service:
            return
        
        # 2. メール検索
        query = (
            f'subject:申込み依頼がございました '
            f'from:info@a-satei.com '
            f'to:kaitori@gigicompany.jp '
            f'newer_than:{days}d'
        )
        self.stdout.write(f"\n検索条件: {query}")
        self.stdout.write(f"最大取得件数: {max_results}")
        
        messages = self._search_messages(service, query, max_results)
        if not messages:
            self.stdout.write(self.style.WARNING("\n該当するメールが見つかりませんでした"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"\n{len(messages)}件のメールが見つかりました"))
        
        # 3. メール詳細取得 & 保存
        saved_count = 0
        skipped_count = 0
        parsed_count = 0
        
        for i, msg in enumerate(messages, 1):
            try:
                # 詳細取得
                detail = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # DB保存
                gmail_message, is_new = self._save_message(detail)
                
                if is_new:
                    saved_count += 1
                    status = self.style.SUCCESS("✓ 新規保存")
                    
                    # 本文をパースして申込情報を抽出
                    if self._parse_and_save_assessment(gmail_message):
                        parsed_count += 1
                        status = self.style.SUCCESS("✓ 新規保存 & 申込情報抽出")
                else:
                    skipped_count += 1
                    status = self.style.WARNING("- スキップ（既存）")
                
                # ヘッダー情報取得
                headers = {h['name']: h['value'] for h in detail.get('payload', {}).get('headers', [])}
                subject = headers.get('Subject', 'N/A')
                
                self.stdout.write(f"  [{i}/{len(messages)}] {status} {subject[:50]}")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [{i}/{len(messages)}] ✗ エラー: {e}"))
        
        # 4. 結果サマリー
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✅ 完了"))
        self.stdout.write(f"  新規保存: {saved_count}件")
        self.stdout.write(f"  申込情報抽出: {parsed_count}件")
        self.stdout.write(f"  スキップ: {skipped_count}件")
        self.stdout.write("=" * 60)
    
    def _build_gmail_service(self):
        """
        Gmail APIサービスを構築（OAuth 2.0方式）
        
        【OAuth 2.0方式の動作】
        1. 初回実行時: ブラウザが開いて認証 → token.json生成
        2. 2回目以降: token.jsonを使って自動実行（ブラウザ不要）
        3. トークン期限切れ時: 自動更新（リフレッシュトークン使用）
        """
        credentials_file = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')
        token_file = os.getenv('GMAIL_TOKEN_FILE', 'token.json')
        scopes = ['https://www.googleapis.com/auth/gmail.readonly']
        
        if not os.path.exists(credentials_file):
            self.stdout.write(self.style.ERROR(
                f"\n❌ エラー: OAuth 2.0クライアントファイルが見つかりません: {credentials_file}"
            ))
            self.stdout.write("\n【対処方法】")
            self.stdout.write("1. Google Cloud ConsoleでOAuth 2.0クライアントIDを作成")
            self.stdout.write("2. credentials.jsonをダウンロードしてプロジェクトルートに配置")
            self.stdout.write("3. 詳細は OAUTH_SETUP.md を参照")
            return None
        
        creds = None
        
        # token.jsonが存在する場合は読み込む
        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(token_file, scopes)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ token.json読み込み失敗: {e}"))
                creds = None
        
        # 認証が必要な場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # トークンをリフレッシュ
                try:
                    self.stdout.write("🔄 アクセストークンを更新中...")
                    creds.refresh(Request())
                    self.stdout.write(self.style.SUCCESS("✓ トークン更新成功"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ トークン更新失敗: {e}"))
                    creds = None
            
            # 新規認証が必要
            if not creds:
                try:
                    self.stdout.write("\n" + "=" * 60)
                    self.stdout.write("🔐 初回認証が必要です")
                    self.stdout.write("=" * 60)
                    self.stdout.write("ブラウザが開きます。Googleアカウントでログインしてください。")
                    self.stdout.write("認証後、このウィンドウに戻ります。")
                    self.stdout.write("")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_file, scopes)
                    creds = flow.run_local_server(port=0)
                    
                    self.stdout.write(self.style.SUCCESS("\n✓ 認証成功"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"\n❌ 認証失敗: {e}"))
                    return None
            
            # token.jsonに保存
            try:
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
                self.stdout.write(self.style.SUCCESS(f"✓ 認証情報を保存: {token_file}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ token.json保存失敗: {e}"))
        
        # Gmail APIサービス構築
        try:
            service = build('gmail', 'v1', credentials=creds)
            self.stdout.write(self.style.SUCCESS("✓ Gmail API接続成功"))
            return service
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Gmail API接続失敗: {e}"))
            return None
    
    def _search_messages(self, service, query, max_results):
        """
        メッセージを検索
        
        【重要】Gmail APIは新しいメールから順に返します
        - maxResults=50 → 最新50件を取得
        - 古いメールは取得されない
        - 1分ごと実行なら、1分間に50件以上来ることはまずないので見逃しなし
        """
        try:
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            # 念のため確認: Gmail APIは新しい順で返すが、ログに件数を出力
            if messages:
                self.stdout.write(f"取得: 最新{len(messages)}件（新しい順）")
            
            return messages
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"メール検索失敗: {e}"))
            return []
    
    def _save_message(self, message_detail):
        """
        メッセージをDBに保存（重複チェック付き）
        
        【重複防止】第1段階: message_id（Gmail固有ID）でチェック
        - 同じメールは絶対に2回保存されない
        - get_or_create()で既存チェック & 新規作成を原子的に実行
        """
        message_id = message_detail['id']
        thread_id = message_detail['threadId']
        
        # ヘッダー情報取得
        headers = {h['name']: h['value'] for h in message_detail.get('payload', {}).get('headers', [])}
        
        # 受信日時（内部タイムスタンプを使用）
        timestamp_ms = int(message_detail['internalDate'])
        received_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        
        # 本文取得
        snippet = message_detail.get('snippet', '')
        body_text = self._extract_body(message_detail)
        
        # 重複チェック & 保存（message_idがUNIQUEなので安全）
        obj, created = GmailMessage.objects.get_or_create(
            message_id=message_id,  # ← UNIQUE制約（重複防止）
            defaults={
                'thread_id': thread_id,
                'from_address': self._extract_email(headers.get('From', '')),
                'to_address': self._extract_email(headers.get('To', '')),
                'subject': headers.get('Subject', ''),
                'received_at': received_at,
                'snippet': snippet,
                'body_text': body_text,
                'raw_json': message_detail,
            }
        )
        
        return obj, created
    
    def _extract_email(self, from_header):
        """メールアドレスを抽出（"Name <email@example.com>" → "email@example.com"）"""
        match = re.search(r'<(.+?)>', from_header)
        if match:
            return match.group(1)
        # <> がない場合はそのまま返す
        return from_header.strip()
    
    def _extract_body(self, message_detail):
        """メール本文を抽出（テキスト形式）"""
        payload = message_detail.get('payload', {})
        
        # マルチパートの場合
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        # シングルパートの場合
        if payload.get('mimeType') == 'text/plain':
            data = payload.get('body', {}).get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        return ''
    
    def _parse_and_save_assessment(self, gmail_message):
        """
        メール本文から申込情報を抽出してCarAssessmentRequestに保存
        
        【重複防止】第2段階: application_number（お申込番号）でチェック
        - 同じ申込番号は絶対に2回保存されない
        - DBレベルでUNIQUE制約があるため完全保証
        """
        if not gmail_message.body_text:
            return False
        
        body = gmail_message.body_text
        
        # 各項目を抽出（「：」の後の値を取得）
        def extract_value(pattern):
            match = re.search(pattern, body)
            return match.group(1).strip() if match else ''
        
        # お申込番号（必須）
        app_number = extract_value(r'お申込番号\s*[：:]\s*(\d+)')
        if not app_number:
            return False  # 申込番号がない場合はスキップ
        
        # 既に同じ申込番号が存在する場合はスキップ（application_numberがUNIQUEなので安全）
        if CarAssessmentRequest.objects.filter(application_number=app_number).exists():
            return False  # ← 重複防止：既存データはスキップ
        
        # お申込日時
        app_datetime_str = extract_value(r'お申込日時\s*[：:]\s*(.+)')
        app_datetime = self._parse_datetime(app_datetime_str)
        
        # 各項目を抽出
        data = {
            'application_number': app_number,
            'application_datetime': app_datetime,
            'desired_sale_timing': extract_value(r'希望売却時期\s*[：:]\s*(.+)'),
            'maker': extract_value(r'メーカー名\s*[：:]\s*(.+)'),
            'car_model': extract_value(r'車種名\s*[：:]\s*(.+)'),
            'year': extract_value(r'年式\s*[：:]\s*(.+)'),
            'mileage': extract_value(r'走行距離\s*[：:]\s*(.+)'),
            'customer_name': extract_value(r'お名前\s*[：:]\s*(.+)'),
            'phone_number': extract_value(r'電話番号\s*[：:]\s*(.+)'),
            'postal_code': extract_value(r'郵便番号\s*[：:]\s*(.+)'),
            'address': extract_value(r'住所\s*[：:]\s*(.+)'),
            'email': extract_value(r'メールアドレス\s*[：:]\s*(.+)'),
            'gmail_message': gmail_message,
        }
        
        # 保存
        try:
            CarAssessmentRequest.objects.create(**data)
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    申込情報の保存に失敗: {e}"))
            return False
    
    def _parse_datetime(self, datetime_str):
        """日時文字列をdatetimeオブジェクトに変換"""
        if not datetime_str:
            return datetime.now(tz=timezone.utc)
        
        try:
            # "2026年02月05日 21:25" 形式をパース
            datetime_str = datetime_str.replace('年', '-').replace('月', '-').replace('日', '')
            dt = datetime.strptime(datetime_str.strip(), '%Y-%m-%d %H:%M')
            # タイムゾーンを付与（日本時間として扱う）
            from zoneinfo import ZoneInfo
            return dt.replace(tzinfo=ZoneInfo('Asia/Tokyo'))
        except Exception:
            return datetime.now(tz=timezone.utc)
