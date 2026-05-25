import os
import json
from datetime import date, datetime, timedelta

from django.utils import timezone
from django.db.models import (
    Case, Count, DecimalField, F, IntegerField, Subquery, OuterRef, Sum, Value, When,
)
from django.db.models.functions import Coalesce
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from leads.models import CarAssessmentRequest, Assessment, SalesProcess


CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CHAT_SCOPES = [
    'https://www.googleapis.com/auth/chat.spaces.readonly',
    'https://www.googleapis.com/auth/chat.messages.readonly',
]


def _self_cc_ratio_text(self_appointments, cc_appointments):
    return None


def _build_sales_financial_kpis(qs):
    """SalesProcess クエリセットから売却・経常利益集計を返す（int 値で返す）"""
    _dec = DecimalField(max_digits=14, decimal_places=0)
    effective_purchase = Case(
        When(
            contract__amount_correction_flag=True,
            contract__corrected_price__isnull=False,
            then=F('contract__corrected_price'),
        ),
        default=F('contract__purchase_price_excl_tax'),
        output_field=_dec,
    )
    totals = qs.aggregate(
        sold_count=Count('id'),
        sold_amount=Coalesce(Sum('sold_price'), Value(0), output_field=_dec),
        purchase_amount=Coalesce(Sum(effective_purchase), Value(0), output_field=_dec),
        total_entry_fee=Coalesce(Sum('sold_destination__entry_fee'), Value(0), output_field=_dec),
        total_contract_fee=Coalesce(Sum('sold_destination__contract_fee'), Value(0), output_field=_dec),
        total_transport_personal=Coalesce(Sum('transport_fee_personal'), Value(0), output_field=_dec),
        total_transport_auction=Coalesce(Sum('transport_fee_auction'), Value(0), output_field=_dec),
        total_other_fee=Coalesce(Sum('other_fee'), Value(0), output_field=_dec),
    )
    sold_amount = int(totals['sold_amount'] or 0)
    total_cost = int(
        (totals['purchase_amount'] or 0) +
        (totals['total_entry_fee'] or 0) +
        (totals['total_contract_fee'] or 0) +
        (totals['total_transport_personal'] or 0) +
        (totals['total_transport_auction'] or 0) +
        (totals['total_other_fee'] or 0)
    )
    return {
        'sold_count': totals['sold_count'],
        'sold_amount': sold_amount,
        'operating_profit': sold_amount - total_cost,
    }


def _build_user_financial_kpis(user, period_start, period_end):
    """ユーザー担当契約の期間内売却・利益集計"""
    if user is None:
        return {'sold_count': 0, 'sold_amount': 0, 'operating_profit': 0}
    qs = SalesProcess.objects.filter(
        sale_done=True,
        sold_price__isnull=False,
        contract__assigned_to=user,
        sold_at__gte=period_start.date(),
        sold_at__lt=period_end.date(),
    )
    return _build_sales_financial_kpis(qs)


def _build_store_kpis(store, period_start, period_end):
    """Store オブジェクトと期間から、所属社員の Assessment ステータス別KPIと財務KPIを返す"""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    store_users = User.objects.filter(
        profile__store=store,
        profile__is_active_employee=True,
        is_active=True,
    )

    base_qs = Assessment.objects.filter(
        assigned_to__in=store_users,
        created_at__gte=period_start,
        created_at__lt=period_end,
    )

    appointments = base_qs.count()
    contracts    = base_qs.filter(status=Assessment.STATUS_CONTRACTED).count()
    lost_count   = base_qs.filter(status=Assessment.STATUS_LOST).count()
    managed_count = base_qs.filter(status=Assessment.STATUS_MANAGED).count()
    pre_cancel   = base_qs.filter(status=Assessment.STATUS_PRE_CANCEL).count()
    close_rate   = round((contracts / appointments) * 100, 1) if appointments else 0.0

    financial_qs = SalesProcess.objects.filter(
        sale_done=True,
        sold_price__isnull=False,
        contract__assigned_to__in=store_users,
        sold_at__gte=period_start.date(),
        sold_at__lt=period_end.date(),
    )
    financial = _build_sales_financial_kpis(financial_qs)

    return {
        'store': store.name,
        'mq': appointments,
        'appointments': appointments,
        'contracts': contracts,
        'close_rate': close_rate,
        'managed_count': managed_count,
        'lost_count': lost_count,
        'pre_assessment_cancel_count': pre_cancel,
        'self_cc_ratio': None,
        'cc_appointments': 0,
        **financial,
    }


def _week_of_month(dt_value):
    return ((dt_value.day - 1) // 7) + 1


def _current_week_range():
    now = timezone.localtime()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    next_week_start = week_start + timedelta(days=7)
    return week_start, next_week_start


def _current_year_range():
    now = timezone.localtime()
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    next_year_start = year_start.replace(year=year_start.year + 1)
    return year_start, next_year_start


def _build_user_kpis(display_name, period_start, period_end, period_label, user=None):
    if user is not None:
        base_qs = Assessment.objects.filter(
            assigned_to=user,
            created_at__gte=period_start,
            created_at__lt=period_end,
        )
        appointment_count           = base_qs.count()
        contract_count              = base_qs.filter(status=Assessment.STATUS_CONTRACTED).count()
        lost_count                  = base_qs.filter(status=Assessment.STATUS_LOST).count()
        managed_count               = base_qs.filter(status=Assessment.STATUS_MANAGED).count()
        pre_assessment_cancel_count = base_qs.filter(status=Assessment.STATUS_PRE_CANCEL).count()
        mq_count = appointment_count
    else:
        appointment_count = contract_count = lost_count = managed_count = pre_assessment_cancel_count = mq_count = 0

    close_rate = round((contract_count / appointment_count) * 100, 1) if appointment_count else 0.0
    financial  = _build_user_financial_kpis(user, period_start, period_end)

    return {
        'period_label': period_label,
        'appointments': appointment_count,
        'contracts': contract_count,
        'close_rate': close_rate,
        'mq': mq_count,
        'self_appointments': 0,
        'cc_appointments': 0,
        'self_cc_ratio': None,
        'managed_count': managed_count,
        'lost_count': lost_count,
        'pre_assessment_cancel_count': pre_assessment_cancel_count,
        **financial,
    }


def get_latest_assessments(limit=100):
    case_id_subq = Assessment.objects.filter(
        assessment_request_id=OuterRef('pk')
    ).values('pk')[:1]
    return CarAssessmentRequest.objects.annotate(
        case_id=Subquery(case_id_subq, output_field=IntegerField())
    ).order_by('-application_datetime')[:limit]


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
    return {
        'month_label': month_start.strftime('%Y-%m'),
        **_build_user_kpis(display_name, month_start, next_month_start, month_start.strftime('%Y年%m月')),
    }


def get_user_period_kpis(display_name, user=None):
    now = timezone.localtime()
    year_start, next_year_start = _current_year_range()
    month_start, next_month_start = _current_month_range()
    week_start, next_week_start = _current_week_range()

    return {
        'year': _build_user_kpis(display_name, year_start, next_year_start, f'{now.year}年', user=user),
        'month': _build_user_kpis(display_name, month_start, next_month_start, f'{now.year}年{now.month}月', user=user),
        'week': _build_user_kpis(display_name, week_start, next_week_start, f'{now.month}月第{_week_of_month(now)}週', user=user),
    }


_SALES_STORE_CODES = ('TSUKUBA', 'MITO', 'OYAMA', 'UTSUNOMIYA')


def _get_sales_stores():
    from accounts.models import Store
    return list(Store.objects.filter(code__in=_SALES_STORE_CODES, is_active=True))


def get_store_performance_summary():
    month_start, next_month_start = _current_month_range()
    return [_build_store_kpis(store, month_start, next_month_start) for store in _get_sales_stores()]


def get_monthly_store_performance_detail():
    month_start, next_month_start = _current_month_range()
    return [_build_store_kpis(store, month_start, next_month_start) for store in _get_sales_stores()]


_SALES_PROCESS_STEPS = [
    ('document_done',  '書類'),
    ('intake_done',    '入庫'),
    ('repair_done',    '加修'),
    ('transport_done', '陸送'),
    ('listing_done',   '出品'),
    ('sale_done',      '売却'),
    ('payment_done',   '入金'),
    ('transfer_done',  '振込'),
]


def get_user_sales_process_next_steps(user):
    """ログインユーザーが担当する売掛管理の未完了レコードと次のステップを返す"""
    if user is None:
        return []

    qs = SalesProcess.objects.filter(
        contract__assigned_to=user,
        transfer_done=False,
    ).select_related(
        'contract',
        'contract__customer',
        'contract__vehicle',
    ).order_by('created_at')

    results = []
    for sp in qs:
        repair_flag = getattr(sp.contract, 'repair_flag', False)
        next_step = None
        for field, label in _SALES_PROCESS_STEPS:
            if field == 'repair_done' and not repair_flag:
                continue
            if not getattr(sp, field):
                next_step = label
                break

        customer = getattr(sp.contract, 'customer', None)
        vehicle  = getattr(sp.contract, 'vehicle', None)
        results.append({
            'id': sp.id,
            'customer_name': customer.name if customer else '-',
            'vehicle_info': f'{vehicle.maker} {vehicle.car_model}' if vehicle else '-',
            'next_step': next_step or '完了待ち',
        })

    return results


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


def get_recent_sale_updates(limit=5):
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


def get_mq_rankings(limit=3):
    month_start, next_month_start = _current_month_range()
    return CarAssessmentRequest.objects.filter(
        application_datetime__gte=month_start,
        application_datetime__lt=next_month_start,
    ).exclude(
        sales_owner_name='',
    ).values(
        'sales_owner_name',
    ).annotate(
        mq_count=Count('id'),
    ).order_by(
        '-mq_count',
        'sales_owner_name',
    )[:limit]


def get_mq_rankings_detail(limit=30):
    month_start, next_month_start = _current_month_range()
    return CarAssessmentRequest.objects.filter(
        application_datetime__gte=month_start,
        application_datetime__lt=next_month_start,
    ).exclude(
        sales_owner_name='',
    ).values(
        'sales_owner_name',
    ).annotate(
        mq_count=Count('id'),
    ).order_by(
        '-mq_count',
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
