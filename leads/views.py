"""
車査定申込一覧画面ビュー
"""
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import datetime
import json
import base64
import logging
from .models import CarAssessmentRequest

logger = logging.getLogger(__name__)


def assessment_list(request):
    """
    車査定申込一覧画面
    初期表示: 新しいレコード100件
    """
    return render(request, 'leads/assessment_list.html')


def get_assessments(request):
    """
    査定申込データを取得するAPIエンドポイント
    
    パラメータ:
    - application_number: お申込番号（完全一致）
    - date_from: お申込日時の開始日（YYYY-MM-DD形式）
    - date_to: お申込日時の終了日（YYYY-MM-DD形式）
    - address: 住所（部分一致）
    - page: ページ番号（デフォルト1）
    - per_page: 1ページあたりの件数（デフォルト100）
    
    検索条件未設定時: 最新100件のみ取得（DB負荷軽減）
    検索条件設定時: 検索結果全件を取得（ページネーション対応）
    """
    # クエリパラメータ取得
    application_number = request.GET.get('application_number', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    address = request.GET.get('address', '').strip()
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 100))
    
    # 検索条件の有無を判定
    has_search_conditions = bool(application_number or date_from or date_to or address)
    
    # ベースクエリ（新しい順）
    queryset = CarAssessmentRequest.objects.all().order_by('-application_datetime')
    
    # 検索条件未設定の場合は100件に制限（DB負荷軽減）
    if not has_search_conditions:
        queryset = queryset[:100]
    
    # フィルタリング（検索条件設定時）
    if application_number:
        queryset = queryset.filter(application_number=application_number)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            queryset = queryset.filter(application_datetime__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            # 終了日は23:59:59まで含める
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(application_datetime__lte=date_to_obj)
        except ValueError:
            pass
    
    if address:
        queryset = queryset.filter(address__icontains=address)
    
    # 総件数を取得
    total_count = queryset.count() if has_search_conditions else min(queryset.count(), 100)
    
    # ページネーション
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)
    
    # JSON形式に変換
    data = []
    for obj in page_obj:
        data.append({
            'id': obj.id,
            'application_number': obj.application_number,
            'application_datetime': timezone.localtime(obj.application_datetime).strftime('%Y-%m-%d %H:%M') if obj.application_datetime else '',
            'desired_sale_timing': obj.desired_sale_timing,
            'maker': obj.maker,
            'car_model': obj.car_model,
            'year': obj.year,
            'mileage': obj.mileage,
            'customer_name': obj.customer_name,
            'phone_number': obj.phone_number,
            'postal_code': obj.postal_code,
            'address': obj.address,
            'email': obj.email,
            'created_at': timezone.localtime(obj.created_at).strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    return JsonResponse({
        'success': True,
        'total_count': total_count,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'per_page': per_page,
        'count': len(data),
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'data': data
    })


def check_new_assessments(request):
    """
    新規レコードをチェックするAPIエンドポイント
    
    パラメータ:
    - last_id: 最後に取得したID（これより大きいIDを取得）
    """
    last_id = request.GET.get('last_id', 0)
    try:
        last_id = int(last_id)
    except ValueError:
        last_id = 0
    
    # last_idより大きいIDのレコードを取得
    new_records = CarAssessmentRequest.objects.filter(id__gt=last_id).order_by('-application_datetime')
    
    data = []
    for obj in new_records:
        data.append({
            'id': obj.id,
            'application_number': obj.application_number,
            'application_datetime': timezone.localtime(obj.application_datetime).strftime('%Y-%m-%d %H:%M') if obj.application_datetime else '',
            'customer_name': obj.customer_name,
            'maker': obj.maker,
            'car_model': obj.car_model,
        })
    
    return JsonResponse({
        'success': True,
        'has_new': len(data) > 0,
        'count': len(data),
        'data': data
    })


@csrf_exempt
@require_POST
def gmail_push_notification(request):
    """
    Gmail Push通知を受信するWebhookエンドポイント
    
    Google Cloud Pub/Subからのメッセージを受信し、新着メールを取得する
    """
    try:
        # リクエストボディをログ出力（デバッグ用）
        logger.info(f'Received request body: {request.body}')
        
        # Pub/Subからのメッセージをパース
        envelope = json.loads(request.body.decode('utf-8'))
        logger.info(f'Parsed envelope: {envelope}')
        
        # messageフィールドを取得
        if 'message' not in envelope:
            logger.warning('No message field in request')
            return HttpResponse(status=400)
        
        message = envelope['message']
        
        # dataフィールドをデコード（Base64エンコードされている）
        if 'data' in message:
            data = base64.b64decode(message['data']).decode('utf-8')
            notification_data = json.loads(data)
            
            logger.info(f'Received push notification: {notification_data}')
            
            # emailAddressとhistoryIdを取得
            email_address = notification_data.get('emailAddress')
            history_id = notification_data.get('historyId')
            
            logger.info(f'Email: {email_address}, HistoryID: {history_id}')
        
        # 非同期でメール取得処理を実行（Celeryなど）
        # または直接実行（簡易版）
        from django.core.management import call_command
        try:
            # バックグラウンドでfetch_gmailを実行
            call_command('fetch_gmail', '--days', '1', '--max', '10')
            logger.info('Email fetch triggered successfully')
        except Exception as e:
            logger.error(f'Failed to fetch emails: {str(e)}')
        
        # Pub/Subには200を返す（確認応答）
        return HttpResponse(status=200)
    
    except json.JSONDecodeError as e:
        logger.error(f'JSON decode error: {str(e)}')
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f'Unexpected error in push notification: {str(e)}')
        return HttpResponse(status=500)
