from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import JsonResponse

from leads.models import CarAssessmentRequest
from .services import (
    get_closed_rankings,
    get_closed_rankings_detail,
    get_latest_assessments,
    get_mq_rankings,
    get_mq_rankings_detail,
    get_monthly_store_performance_detail,
    get_recent_appointment_updates,
    get_recent_appointment_updates_detail,
    get_recent_closed_updates,
    get_recent_closed_updates_detail,
    get_recent_sale_updates,
    get_store_performance_summary,
    get_user_period_kpis,
    get_upcoming_calendar_events,
    get_recent_chat_messages,
)


@login_required
@require_GET
def dashboard(request):
    current_user_display_name = request.user.get_full_name().strip() or request.user.username
    latest_assessments = get_latest_assessments(limit=100)
    recent_appointment_updates = get_recent_appointment_updates(limit=3)
    recent_closed_updates = get_recent_closed_updates(limit=3)
    recent_sale_updates = get_recent_sale_updates(limit=3)
    closed_rankings = get_closed_rankings(limit=3)
    mq_rankings = get_mq_rankings(limit=3)
    period_kpis = get_user_period_kpis(current_user_display_name)
    monthly_kpis = period_kpis.get('month', {})
    store_performance_summary = get_store_performance_summary()

    return render(request, 'home/dashboard.html', {
        'latest_assessments': latest_assessments,
        'recent_appointment_updates': recent_appointment_updates,
        'recent_closed_updates': recent_closed_updates,
        'recent_sale_updates': recent_sale_updates,
        'closed_rankings': closed_rankings,
        'mq_rankings': mq_rankings,
        'monthly_kpis': monthly_kpis,
        'period_kpis': period_kpis,
        'store_performance_summary': store_performance_summary,
        'current_user_display_name': current_user_display_name,
        'follow_status_choices': [choice[0] for choice in CarAssessmentRequest.FOLLOW_STATUS_CHOICES],
    })


@login_required
@require_GET
def board_detail(request, section):
    section = (section or '').strip()

    if section == 'sales-appointments':
        rows = get_recent_appointment_updates_detail(limit=50)
        context = {
            'page_title': '営業予定速報 詳細',
            'headers': ['更新日時', '申込番号', 'お名前', '担当営業', '住所'],
            'records': [
                [
                    row.get('status_updated_at'),
                    row.get('application_number'),
                    row.get('customer_name'),
                    row.get('sales_owner_name') or '-',
                    row.get('address') or '-',
                ] for row in rows
            ],
            'datetime_indexes': [0],
        }
    elif section == 'sales-closed':
        rows = get_recent_closed_updates_detail(limit=50)
        context = {
            'page_title': '成約速報 詳細',
            'headers': ['更新日時', '申込番号', 'お名前', '担当営業', '住所'],
            'records': [
                [
                    row.get('status_updated_at'),
                    row.get('application_number'),
                    row.get('customer_name'),
                    row.get('sales_owner_name') or '-',
                    row.get('address') or '-',
                ] for row in rows
            ],
            'datetime_indexes': [0],
        }
    elif section == 'store-performance':
        rows = get_monthly_store_performance_detail()
        context = {
            'page_title': '店舗別実績 詳細（当月）',
            'headers': ['店舗', 'MQ', '商談数', '契約数', '契約率', '自アポ：CC'],
            'records': [
                [
                    row.get('store'),
                    row.get('mq'),
                    row.get('appointments'),
                    row.get('contracts'),
                    f"{row.get('close_rate')}%",
                    row.get('self_cc_ratio'),
                ] for row in rows
            ],
            'datetime_indexes': [],
        }
    elif section == 'rank-closed':
        rows = get_closed_rankings_detail(limit=30)
        context = {
            'page_title': '成約ランキング 詳細',
            'headers': ['順位', '担当営業', '成約件数'],
            'records': [[index + 1, row.get('sales_owner_name'), row.get('closed_count')] for index, row in enumerate(rows)],
            'datetime_indexes': [],
        }
    elif section == 'rank-mq':
        rows = get_mq_rankings_detail(limit=30)
        context = {
            'page_title': 'MQランキング 詳細（当月）',
            'headers': ['順位', '担当営業', 'MQ件数'],
            'records': [[index + 1, row.get('sales_owner_name'), row.get('mq_count')] for index, row in enumerate(rows)],
            'datetime_indexes': [],
        }
    else:
        context = {
            'page_title': '詳細情報',
            'headers': [],
            'records': [],
            'datetime_indexes': [],
            'message': 'このセクションの詳細は準備中です。',
        }

    return render(request, 'home/board_detail.html', context)


@login_required
@require_GET
def calendar_events_api(request):
    result = get_upcoming_calendar_events(limit=10)
    return JsonResponse(result)


@login_required
@require_GET
def chat_messages_api(request):
    result = get_recent_chat_messages(limit_spaces=3, messages_per_space=3)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def google_chat_webhook(request):
    return JsonResponse({'text': 'ok', 'status': 'ready'})
