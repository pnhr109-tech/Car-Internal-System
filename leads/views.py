"""
車査定申込一覧画面ビュー
"""
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login, logout
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from datetime import datetime
import json
import base64
import logging
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .models import CarAssessmentRequest

logger = logging.getLogger(__name__)


@require_GET
def google_login_page(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    return render(request, 'leads/google_login.html', {
        'google_client_id': settings.GOOGLE_CLIENT_ID,
        'allowed_domain': settings.ALLOWED_GOOGLE_DOMAIN,
    })


@require_POST
def google_login(request):
    credential = request.POST.get('credential', '').strip()

    if not settings.GOOGLE_CLIENT_ID:
        return HttpResponse('GOOGLE_CLIENT_ID が未設定です', status=500)

    if not credential:
        return HttpResponse('Google認証情報がありません', status=400)

    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception:
        return HttpResponse('Googleトークンの検証に失敗しました', status=401)

    email = idinfo.get('email', '').lower()
    email_verified = idinfo.get('email_verified', False)
    hosted_domain = idinfo.get('hd', '').lower()
    allowed_domain = settings.ALLOWED_GOOGLE_DOMAIN.lower()

    is_allowed_domain = email.endswith(f'@{allowed_domain}')
    if hosted_domain:
        is_allowed_domain = is_allowed_domain and hosted_domain == allowed_domain

    if not email or not email_verified or not is_allowed_domain:
        return HttpResponse('gigicompanyのアカウントのみログイン可能です', status=403)

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            'email': email,
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'is_active': True,
        }
    )

    if not user.is_active:
        return HttpResponse('このアカウントは無効化されています', status=403)

    # 既存ユーザーの表示名情報を更新（空のときのみ）
    updated = False
    if not user.first_name and idinfo.get('given_name'):
        user.first_name = idinfo.get('given_name')
        updated = True
    if not user.last_name and idinfo.get('family_name'):
        user.last_name = idinfo.get('family_name')
        updated = True
    if not user.email:
        user.email = email
        updated = True
    if updated:
        user.save(update_fields=['first_name', 'last_name', 'email'])

    login(request, user)
    return JsonResponse({'success': True, 'redirect': settings.LOGIN_REDIRECT_URL})


@require_GET
def logout_view(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@login_required
def assessment_list(request):
    """
    車査定申込一覧画面
    初期表示: 新しいレコード100件
    """
    return render(request, 'leads/assessment_list.html')


@login_required
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
    
    # JSON形式に変換（必要カラムのみ取得して軽量化）
    page_rows = page_obj.object_list.values(
        'id',
        'application_number',
        'application_datetime',
        'desired_sale_timing',
        'maker',
        'car_model',
        'year',
        'mileage',
        'customer_name',
        'phone_number',
        'postal_code',
        'address',
        'email',
        'created_at',
    )

    data = []
    for row in page_rows:
        application_datetime = row.get('application_datetime')
        created_at = row.get('created_at')
        data.append({
            'id': row['id'],
            'application_number': row['application_number'],
            'application_datetime': timezone.localtime(application_datetime).strftime('%Y-%m-%d %H:%M') if application_datetime else '',
            'desired_sale_timing': row['desired_sale_timing'],
            'maker': row['maker'],
            'car_model': row['car_model'],
            'year': row['year'],
            'mileage': row['mileage'],
            'customer_name': row['customer_name'],
            'phone_number': row['phone_number'],
            'postal_code': row['postal_code'],
            'address': row['address'],
            'email': row['email'],
            'created_at': timezone.localtime(created_at).strftime('%Y-%m-%d %H:%M:%S') if created_at else '',
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


@login_required
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
    
    # last_idより大きいIDのレコードを取得（ポーリング向けに必要カラムのみ）
    new_records = CarAssessmentRequest.objects.filter(id__gt=last_id).order_by('-id').values(
        'id',
        'application_number',
        'application_datetime',
        'customer_name',
        'maker',
        'car_model',
    )

    data = []
    for row in new_records:
        app_datetime = row.get('application_datetime')
        data.append({
            'id': row['id'],
            'application_number': row['application_number'],
            'application_datetime': timezone.localtime(app_datetime).strftime('%Y-%m-%d %H:%M') if app_datetime else '',
            'customer_name': row['customer_name'],
            'maker': row['maker'],
            'car_model': row['car_model'],
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
    lock_key = 'gmail_push:fetch_lock'
    lock_acquired = False
    dedupe_key = None

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

            # 重複通知抑止（historyId単位で短時間の再実行を防止）
            if email_address and history_id:
                dedupe_key = f'gmail_push:history:{email_address}:{history_id}'
                is_new_notification = cache.add(dedupe_key, '1', timeout=600)  # 10分
                if not is_new_notification:
                    logger.info(f'Duplicate push notification skipped: {dedupe_key}')
                    return HttpResponse(status=200)

        # fetch_gmail の同時実行制御（多重起動を防止）
        lock_acquired = cache.add(lock_key, '1', timeout=300)  # 5分
        if not lock_acquired:
            logger.info('fetch_gmail is already running. Skip this push trigger.')
            return HttpResponse(status=200)
        
        # 非同期でメール取得処理を実行（Celeryなど）
        # または直接実行（簡易版）
        from django.core.management import call_command
        try:
            # バックグラウンドでfetch_gmailを実行
            call_command('fetch_gmail', '--days', '1', '--max', '10')
            logger.info('Email fetch triggered successfully')
        except Exception as e:
            # fetch失敗時は同一historyIdを再試行できるようにする
            if dedupe_key:
                cache.delete(dedupe_key)
            logger.error(f'Failed to fetch emails: {str(e)}')
        
        # Pub/Subには200を返す（確認応答）
        return HttpResponse(status=200)
    
    except json.JSONDecodeError as e:
        logger.error(f'JSON decode error: {str(e)}')
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f'Unexpected error in push notification: {str(e)}')
        return HttpResponse(status=500)
    finally:
        if lock_acquired:
            cache.delete(lock_key)
