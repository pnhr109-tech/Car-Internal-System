import os
import json
from datetime import date, datetime

from django.utils import timezone
from django.db.models import Count
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from leads.models import CarAssessmentRequest


CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CHAT_SCOPES = [
    'https://www.googleapis.com/auth/chat.spaces.readonly',
    'https://www.googleapis.com/auth/chat.messages.readonly',
]


def get_latest_assessments(limit=100):
    return CarAssessmentRequest.objects.order_by('-application_datetime')[:limit]


def _current_month_range():
    now = timezone.localtime()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)
    return month_start, next_month_start


def get_user_monthly_kpis(display_name):
    month_start, next_month_start = _current_month_range()

    appointment_count = CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_APPOINTMENT,
        status_updated_by=display_name,
        status_updated_at__gte=month_start,
        status_updated_at__lt=next_month_start,
    ).count()

    contract_count = CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_CLOSED,
        status_updated_by=display_name,
        status_updated_at__gte=month_start,
        status_updated_at__lt=next_month_start,
    ).count()

    mq_count = CarAssessmentRequest.objects.filter(
        sales_owner_name=display_name,
        application_datetime__gte=month_start,
        application_datetime__lt=next_month_start,
    ).count()

    close_rate = round((contract_count / appointment_count) * 100, 1) if appointment_count else 0.0

    return {
        'month_label': month_start.strftime('%Y-%m'),
        'appointments': appointment_count,
        'contracts': contract_count,
        'close_rate': close_rate,
        'mq': mq_count,
    }


def get_store_performance_summary():
    month_start, next_month_start = _current_month_range()
    month_queryset = CarAssessmentRequest.objects.filter(
        application_datetime__gte=month_start,
        application_datetime__lt=next_month_start,
    )

    stores = [
        ('つくば', 'つくば'),
        ('水戸', '水戸'),
        ('小山', '小山'),
    ]

    summary = []
    for label, keyword in stores:
        store_queryset = month_queryset.filter(address__icontains=keyword)
        mq = store_queryset.count()
        appointments = store_queryset.filter(follow_status=CarAssessmentRequest.STATUS_APPOINTMENT).count()
        contracts = store_queryset.filter(follow_status=CarAssessmentRequest.STATUS_CLOSED).count()
        close_rate = round((contracts / appointments) * 100, 1) if appointments else 0.0
        summary.append({
            'store': label,
            'mq': mq,
            'appointments': appointments,
            'contracts': contracts,
            'close_rate': close_rate,
        })
    return summary


def get_monthly_store_performance_detail():
    month_start, next_month_start = _current_month_range()
    month_queryset = CarAssessmentRequest.objects.filter(
        application_datetime__gte=month_start,
        application_datetime__lt=next_month_start,
    )

    records = []
    for store_label, keyword in [('つくば', 'つくば'), ('水戸', '水戸'), ('小山', '小山')]:
        store_queryset = month_queryset.filter(address__icontains=keyword)
        mq = store_queryset.count()
        appointments = store_queryset.filter(follow_status=CarAssessmentRequest.STATUS_APPOINTMENT).count()
        contracts = store_queryset.filter(follow_status=CarAssessmentRequest.STATUS_CLOSED).count()
        close_rate = round((contracts / appointments) * 100, 1) if appointments else 0.0
        records.append({
            'store': store_label,
            'mq': mq,
            'appointments': appointments,
            'contracts': contracts,
            'close_rate': close_rate,
        })
    return records


def get_recent_appointment_updates_detail(limit=50):
    return CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_APPOINTMENT,
        status_updated_at__isnull=False,
    ).order_by('-status_updated_at').values(
        'application_number',
        'customer_name',
        'sales_owner_name',
        'status_updated_at',
        'address',
    )[:limit]


def get_recent_closed_updates_detail(limit=50):
    return CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_CLOSED,
        status_updated_at__isnull=False,
    ).order_by('-status_updated_at').values(
        'application_number',
        'customer_name',
        'sales_owner_name',
        'status_updated_at',
        'address',
    )[:limit]


def get_closed_rankings_detail(limit=30):
    return CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_CLOSED,
    ).exclude(
        sales_owner_name='',
    ).values(
        'sales_owner_name',
    ).annotate(
        closed_count=Count('id'),
    ).order_by(
        '-closed_count',
        'sales_owner_name',
    )[:limit]


def get_recent_appointment_updates(limit=8):
    return CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_APPOINTMENT,
        status_updated_at__isnull=False,
    ).order_by('-status_updated_at').values(
        'id',
        'application_number',
        'customer_name',
        'sales_owner_name',
        'status_updated_at',
    )[:limit]


def get_recent_closed_updates(limit=5):
    return CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_CLOSED,
        status_updated_at__isnull=False,
    ).order_by('-status_updated_at').values(
        'id',
        'application_number',
        'customer_name',
        'sales_owner_name',
        'status_updated_at',
    )[:limit]


def get_closed_rankings(limit=3):
    return CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_CLOSED,
    ).exclude(
        sales_owner_name='',
    ).values(
        'sales_owner_name',
    ).annotate(
        closed_count=Count('id'),
    ).order_by(
        '-closed_count',
        'sales_owner_name',
    )[:limit]


def _get_google_credentials(required_scopes):
    credentials_file = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')
    token_file = os.getenv('GOOGLE_WORKSPACE_TOKEN_FILE', 'token_workspace.json')

    if not os.path.exists(credentials_file):
        return None, 'Google認証ファイル(credentials.json)が見つかりません。'

    if not os.path.exists(token_file):
        return None, f'Google Workspaceトークン({token_file})が見つかりません。setup_google_workspace_token を実行してください。'

    try:
        with open(token_file, 'r', encoding='utf-8') as token_handle:
            token_payload = json.load(token_handle)
        granted_scopes = set(token_payload.get('scopes') or [])
        missing_scopes = [scope for scope in required_scopes if scope not in granted_scopes]
        if missing_scopes:
            return None, 'Googleトークンの権限が不足しています。setup_google_workspace_token を実行して再認証してください。'
    except Exception:
        return None, f'{token_file} の読み込みに失敗しました。setup_google_workspace_token で再作成してください。'

    try:
        creds = Credentials.from_authorized_user_file(token_file, required_scopes)
    except Exception:
        return None, f'{token_file} の読み込みに失敗しました。setup_google_workspace_token で再作成してください。'

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_file, 'w', encoding='utf-8') as token_handle:
                    token_handle.write(creds.to_json())
            except Exception:
                return None, 'Googleトークンの更新に失敗しました。再認証してください。'
        else:
            return None, 'Googleトークンが無効です。再認証してください。'

    if not creds.has_scopes(required_scopes):
        return None, 'Googleトークンに必要な権限(scope)が不足しています。setup_google_workspace_token を実行して再認証してください。'

    return creds, ''


def _parse_google_datetime(value):
    if not value:
        return None

    try:
        normalized = value.replace('Z', '+00:00')
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())

    return timezone.localtime(parsed)


def _extract_http_error_message(error):
    try:
        payload = json.loads(error.content.decode('utf-8'))
        return payload.get('error', {}).get('message') or str(error)
    except Exception:
        return str(error)


def get_upcoming_calendar_events(limit=10):
    creds, error_message = _get_google_credentials(CALENDAR_SCOPES)
    if not creds:
        return {
            'success': False,
            'message': error_message,
            'items': [],
        }

    try:
        service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
        response = service.events().list(
            calendarId='primary',
            timeMin=timezone.now().isoformat(),
            maxResults=limit,
            singleEvents=True,
            orderBy='startTime',
        ).execute()
    except HttpError as error:
        return {
            'success': False,
            'message': f'カレンダー取得に失敗しました: {_extract_http_error_message(error)}',
            'items': [],
        }

    items = []
    for event in response.get('items', []):
        start_info = event.get('start', {})
        date_time_value = start_info.get('dateTime')
        date_value = start_info.get('date')

        if date_time_value:
            local_dt = _parse_google_datetime(date_time_value)
            start_label = local_dt.strftime('%m/%d %H:%M') if local_dt else date_time_value
        elif date_value:
            try:
                start_label = datetime.fromisoformat(date_value).strftime('%m/%d 終日')
            except ValueError:
                start_label = f'{date_value} 終日'
        else:
            start_label = '-'

        items.append({
            'summary': event.get('summary') or '(タイトル未設定)',
            'start': start_label,
            'location': event.get('location') or '-',
            'link': event.get('htmlLink') or 'https://calendar.google.com/',
        })

    return {
        'success': True,
        'message': '',
        'items': items,
    }


def get_recent_chat_messages(limit_spaces=3, messages_per_space=3):
    creds, error_message = _get_google_credentials(CHAT_SCOPES)
    if not creds:
        return {
            'success': False,
            'message': error_message,
            'items': [],
        }

    try:
        service = build('chat', 'v1', credentials=creds, cache_discovery=False)
        spaces_response = service.spaces().list(pageSize=limit_spaces).execute()
    except HttpError as error:
        detailed = _extract_http_error_message(error)
        if 'Google Chat app not found' in detailed:
            detailed = 'Google Chat API の「Configuration」で Chat アプリを作成・有効化してください。'
        return {
            'success': False,
            'message': f'チャット取得に失敗しました: {detailed}',
            'items': [],
        }

    space_items = spaces_response.get('spaces', [])
    flattened_messages = []

    for space in space_items:
        space_name = space.get('name')
        if not space_name:
            continue

        space_label = space.get('displayName') or 'スペース'

        try:
            message_response = service.spaces().messages().list(
                parent=space_name,
                pageSize=messages_per_space,
            ).execute()
        except HttpError:
            continue

        for message in message_response.get('messages', []):
            created_at = _parse_google_datetime(message.get('createTime'))
            created_label = created_at.strftime('%m/%d %H:%M') if created_at else '-'
            sender = message.get('sender', {}).get('displayName') or '-'

            flattened_messages.append({
                'space': space_label,
                'text': message.get('text') or '(本文なし)',
                'sender': sender,
                'time': created_label,
                'link': 'https://chat.google.com/',
            })

    if not flattened_messages:
        return {
            'success': True,
            'message': '',
            'items': [],
        }

    flattened_messages.sort(key=lambda item: item['time'], reverse=True)

    return {
        'success': True,
        'message': '',
        'items': flattened_messages[: max(messages_per_space * limit_spaces, 1)],
    }
