from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import F, Q, Max
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from datetime import datetime
import json
import base64
import logging

from .models import (
    Assessment,
    CarAssessmentRequest,
    ContactHistory,
    Customer,
    PurchaseContract,
    Vehicle,
)

logger = logging.getLogger(__name__)


def _current_user_display_name(user):
    full_name = user.get_full_name().strip()
    return full_name or user.username


@login_required
def assessment_list(request):
    """査定申込一覧"""
    return render(request, 'leads/assessment_list.html', {
        'current_user_display_name': _current_user_display_name(request.user),
        'follow_status_choices': [choice[0] for choice in CarAssessmentRequest.FOLLOW_STATUS_CHOICES],
        'channel_choices': CarAssessmentRequest.CHANNEL_CHOICES,
    })


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
        'call_count',
        'postal_code',
        'address',
        'email',
        'sales_owner_name',
        'sales_assigned_at',
        'follow_status',
        'sales_note',
        'status_updated_at',
        'status_updated_by',
        'created_at',
    )

    data = []
    for row in page_rows:
        application_datetime = row.get('application_datetime')
        created_at = row.get('created_at')
        sales_assigned_at = row.get('sales_assigned_at')
        status_updated_at = row.get('status_updated_at')
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
            'call_count': row['call_count'],
            'postal_code': row['postal_code'],
            'address': row['address'],
            'email': row['email'],
            'sales_owner_name': row['sales_owner_name'],
            'sales_assigned_at': timezone.localtime(sales_assigned_at).strftime('%Y-%m-%d %H:%M') if sales_assigned_at else '',
            'follow_status': row['follow_status'],
            'sales_note': row['sales_note'],
            'status_updated_at': timezone.localtime(status_updated_at).strftime('%Y-%m-%d %H:%M') if status_updated_at else '',
            'status_updated_by': row['status_updated_by'],
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


@login_required
def get_latest_assessment_id(request):
    latest_id = CarAssessmentRequest.objects.aggregate(max_id=Max('id')).get('max_id') or 0
    return JsonResponse({
        'success': True,
        'latest_id': latest_id,
    })


@login_required
def get_assessment_detail(request, request_id):
    target = CarAssessmentRequest.objects.filter(id=request_id).values(
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
        'call_count',
        'postal_code',
        'address',
        'email',
        'sales_owner_name',
        'sales_assigned_at',
        'follow_status',
        'sales_note',
        'status_updated_at',
        'status_updated_by',
        'created_at',
    ).first()

    if not target:
        return JsonResponse({'success': False, 'message': '対象データが存在しません'}, status=404)

    def fmt(dt_value, pattern):
        if not dt_value:
            return ''
        return timezone.localtime(dt_value).strftime(pattern)

    data = {
        **target,
        'application_datetime': fmt(target.get('application_datetime'), '%Y-%m-%d %H:%M'),
        'sales_assigned_at': fmt(target.get('sales_assigned_at'), '%Y-%m-%d %H:%M'),
        'status_updated_at': fmt(target.get('status_updated_at'), '%Y-%m-%d %H:%M'),
        'created_at': fmt(target.get('created_at'), '%Y-%m-%d %H:%M:%S'),
    }

    return JsonResponse({'success': True, 'data': data})


@login_required
@require_POST
def claim_assessment_owner(request, request_id):
    sales_name = _current_user_display_name(request.user)

    try:
        with transaction.atomic():
            target = CarAssessmentRequest.objects.select_for_update().filter(id=request_id).first()
            if not target:
                return JsonResponse({'success': False, 'message': '対象データが存在しません'}, status=404)

            if target.sales_owner_name:
                return JsonResponse({
                    'success': False,
                    'message': f'すでに担当営業が確定しています（{target.sales_owner_name}）',
                    'sales_owner_name': target.sales_owner_name,
                }, status=409)

            if target.follow_status != CarAssessmentRequest.STATUS_UNTOUCHED:
                return JsonResponse({
                    'success': False,
                    'message': '未対応の案件のみ挙手できます',
                }, status=400)

            now = timezone.now()
            target.sales_owner_name = sales_name
            target.sales_assigned_at = now
            target.status_updated_by = sales_name
            target.status_updated_at = now
            target.save(update_fields=['sales_owner_name', 'sales_assigned_at', 'status_updated_by', 'status_updated_at', 'updated_at'])
    except Exception as exc:
        logger.error(f'claim_assessment_owner failed: request_id={request_id}, error={exc}')
        return JsonResponse({'success': False, 'message': '担当営業の登録に失敗しました'}, status=500)

    return JsonResponse({
        'success': True,
        'message': '担当営業として登録しました',
        'sales_owner_name': sales_name,
    })


@login_required
@require_POST
def increment_assessment_call_count(request, request_id):
    try:
        with transaction.atomic():
            target = CarAssessmentRequest.objects.select_for_update().filter(id=request_id).first()
            if not target:
                return JsonResponse({'success': False, 'message': '対象データが存在しません'}, status=404)

            target.call_count = F('call_count') + 1
            target.save(update_fields=['call_count', 'updated_at'])
            target.refresh_from_db(fields=['call_count'])
    except Exception as exc:
        logger.error(f'increment_assessment_call_count failed: request_id={request_id}, error={exc}')
        return JsonResponse({'success': False, 'message': '通話数の更新に失敗しました'}, status=500)

    return JsonResponse({
        'success': True,
        'call_count': target.call_count,
    })


@login_required
@require_POST
def update_assessment_follow_status(request, request_id):
    sales_name = _current_user_display_name(request.user)

    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    follow_status = str(payload.get('follow_status', '')).strip()
    sales_note = str(payload.get('sales_note', '')).strip()
    allowed_statuses = {choice[0] for choice in CarAssessmentRequest.FOLLOW_STATUS_CHOICES}

    if follow_status not in allowed_statuses:
        return JsonResponse({'success': False, 'message': '対応ステータスが不正です'}, status=400)

    try:
        with transaction.atomic():
            target = CarAssessmentRequest.objects.select_for_update().filter(id=request_id).first()
            if not target:
                return JsonResponse({'success': False, 'message': '対象データが存在しません'}, status=404)

            if not target.sales_owner_name:
                if follow_status != CarAssessmentRequest.STATUS_APPOINTMENT:
                    return JsonResponse({'success': False, 'message': '担当未確定の案件は商談確定で更新してください'}, status=400)

                target.sales_owner_name = sales_name
                target.sales_assigned_at = timezone.now()

            if target.sales_owner_name != sales_name:
                return JsonResponse({
                    'success': False,
                    'message': f'担当営業（{target.sales_owner_name}）のみ更新できます',
                }, status=403)

            now = timezone.now()
            target.follow_status = follow_status
            target.sales_note = sales_note
            target.status_updated_by = sales_name
            target.status_updated_at = now
            target.save(update_fields=['sales_owner_name', 'sales_assigned_at', 'follow_status', 'sales_note', 'status_updated_by', 'status_updated_at', 'updated_at'])
    except Exception as exc:
        logger.error(f'update_assessment_follow_status failed: request_id={request_id}, error={exc}')
        return JsonResponse({'success': False, 'message': 'ステータス更新に失敗しました'}, status=500)

    return JsonResponse({
        'success': True,
        'message': 'ステータスを更新しました',
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


# ===========================================================================
# 査定申込 詳細・新規作成
# ===========================================================================

@login_required
def assessment_detail(request, pk):
    """査定申込詳細・変更（S02）"""
    req = get_object_or_404(CarAssessmentRequest, pk=pk)
    histories = req.contact_histories.select_related('recorded_by').order_by('-contacted_at')
    can_promote = (
        req.follow_status == CarAssessmentRequest.STATUS_APPOINTMENT
        and not hasattr(req, 'assessment')
    )
    # Assessment が存在するか safe に確認
    try:
        linked_assessment = req.assessment
    except Assessment.DoesNotExist:
        linked_assessment = None

    return render(request, 'leads/assessment_detail.html', {
        'req': req,
        'histories': histories,
        'can_promote': can_promote,
        'linked_assessment': linked_assessment,
        'follow_status_choices': CarAssessmentRequest.FOLLOW_STATUS_CHOICES,
        'channel_choices': CarAssessmentRequest.CHANNEL_CHOICES,
    })


@login_required
def assessment_create(request):
    """査定申込手動入力（S03）"""
    if request.method == 'POST':
        # 顧客を取得 or 作成
        customer_id = request.POST.get('customer_id')
        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)
        else:
            customer = Customer.objects.create(
                name=request.POST.get('customer_name', ''),
                phone_number=request.POST.get('phone_number', ''),
                email=request.POST.get('email', ''),
                postal_code=request.POST.get('postal_code', ''),
                address=request.POST.get('address', ''),
                updated_by=request.user,
            )

        # 車両を作成
        vehicle = Vehicle.objects.create(
            maker=request.POST.get('maker', ''),
            car_model=request.POST.get('car_model', ''),
            year=request.POST.get('year', ''),
            mileage=request.POST.get('mileage', ''),
            updated_by=request.user,
        )

        # 申込番号を自動生成（MANUAL-YYYYMMDD-連番）
        today_str = timezone.localdate(timezone.now()).strftime('%Y%m%d')
        prefix = f'MANUAL-{today_str}-'
        last = CarAssessmentRequest.objects.filter(
            application_number__startswith=prefix
        ).order_by('-application_number').first()
        seq = int(last.application_number.split('-')[-1]) + 1 if last else 1
        application_number = f'{prefix}{seq:04d}'

        reservation_raw = request.POST.get('reservation_datetime', '')
        reservation_dt = None
        if reservation_raw:
            try:
                reservation_dt = datetime.strptime(reservation_raw, '%Y-%m-%dT%H:%M')
                reservation_dt = timezone.make_aware(reservation_dt)
            except ValueError:
                pass

        req = CarAssessmentRequest.objects.create(
            application_number=application_number,
            application_datetime=timezone.now(),
            channel_type=request.POST.get('channel_type', CarAssessmentRequest.CHANNEL_MANUAL),
            customer=customer,
            vehicle=vehicle,
            customer_name=customer.name,
            phone_number=customer.phone_number,
            email=customer.email,
            postal_code=customer.postal_code,
            address=customer.address,
            maker=vehicle.maker,
            car_model=vehicle.car_model,
            year=vehicle.year,
            mileage=vehicle.mileage,
            assigned_to=request.user,
            sales_owner_name=_current_user_display_name(request.user),
            sales_assigned_at=timezone.now(),
            referral_name=request.POST.get('referral_name', ''),
            reservation_datetime=reservation_dt,
            desired_sale_timing=request.POST.get('desired_sale_timing', ''),
            sales_note=request.POST.get('sales_note', ''),
            follow_status=CarAssessmentRequest.STATUS_UNTOUCHED,
        )
        messages.success(request, f'査定申込を登録しました（{application_number}）')
        return redirect('leads:assessment_detail', pk=req.pk)

    # GET: 顧客検索
    customer_search = request.GET.get('customer_search', '').strip()
    found_customers = []
    if customer_search:
        found_customers = Customer.objects.filter(
            Q(name__icontains=customer_search) | Q(phone_number__icontains=customer_search)
        )[:10]

    return render(request, 'leads/assessment_create.html', {
        'channel_choices': CarAssessmentRequest.CHANNEL_CHOICES,
        'customer_search': customer_search,
        'found_customers': found_customers,
    })


# ===========================================================================
# 案件一覧・詳細（S04・S05）
# ===========================================================================

@login_required
def case_list(request):
    """案件一覧（S05）— 商談昇格済みの申込"""
    qs = Assessment.objects.select_related(
        'assessment_request', 'customer', 'vehicle', 'assigned_to', 'approved_by'
    ).order_by('-created_at')

    profile = getattr(request.user, 'profile', None)

    # 権限によるフィルタリング
    if profile and not profile.has_global_access:
        if profile.role == profile.ROLE_GENERAL:
            qs = qs.filter(assigned_to=request.user)
        else:
            store_users = profile.store.members.values_list('user_id', flat=True) if profile.store else []
            qs = qs.filter(assigned_to__in=store_users)

    # 検索
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if q:
        qs = qs.filter(Q(customer__name__icontains=q) | Q(customer__phone_number__icontains=q) | Q(vehicle__maker__icontains=q) | Q(vehicle__car_model__icontains=q))
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'leads/case_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status': status,
        'status_choices': Assessment.STATUS_CHOICES,
    })


@login_required
def case_detail(request, pk):
    """案件詳細（S04）— 商談・契約タブ一気通貫"""
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            'assessment_request', 'customer', 'vehicle', 'assigned_to', 'approved_by'
        ),
        pk=pk,
    )
    try:
        contract = assessment.contract
    except PurchaseContract.DoesNotExist:
        contract = None

    histories = assessment.assessment_request.contact_histories.select_related('recorded_by').order_by('-contacted_at')
    check_items = assessment.check_items.all()
    documents = contract.documents.select_related('document_type').all() if contract else []
    identity_docs = contract.identity_documents.all() if contract else []
    bank_accounts = assessment.customer.bank_accounts.all()
    vehicle_images = assessment.vehicle.images.all()

    active_tab = request.GET.get('tab', 'assessment')

    profile = getattr(request.user, 'profile', None)
    can_approve = profile.can_approve if profile else request.user.is_superuser

    return render(request, 'leads/case_detail.html', {
        'assessment': assessment,
        'contract': contract,
        'histories': histories,
        'check_items': check_items,
        'documents': documents,
        'identity_docs': identity_docs,
        'bank_accounts': bank_accounts,
        'vehicle_images': vehicle_images,
        'active_tab': active_tab,
        'can_approve': can_approve,
        'assessment_status_choices': Assessment.STATUS_CHOICES,
        'contract_status_choices': PurchaseContract.STATUS_CHOICES if contract else [],
    })


# ===========================================================================
# 契約一覧（S06）
# ===========================================================================

@login_required
def contract_list(request):
    """契約一覧（S06）"""
    qs = PurchaseContract.objects.select_related(
        'assessment', 'customer', 'vehicle', 'assigned_to'
    ).order_by('-contract_date')

    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_global_access:
        if profile.role == profile.ROLE_GENERAL:
            qs = qs.filter(assigned_to=request.user)
        else:
            store_users = profile.store.members.values_list('user_id', flat=True) if profile.store else []
            qs = qs.filter(assigned_to__in=store_users)

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if q:
        qs = qs.filter(Q(customer__name__icontains=q) | Q(customer__phone_number__icontains=q))
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'leads/contract_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status': status,
        'status_choices': PurchaseContract.STATUS_CHOICES,
    })


# ===========================================================================
# 承認待ち一覧（S07）
# ===========================================================================

@login_required
def approval_list(request):
    """承認待ち一覧（S07）"""
    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.can_approve) and not request.user.is_superuser:
        messages.error(request, '承認権限がありません')
        return redirect('leads:assessment_list')

    pending_assessments = Assessment.objects.filter(
        approved_by__isnull=True,
        status=Assessment.STATUS_IN_PROGRESS,
    ).select_related('customer', 'vehicle', 'assigned_to').order_by('-created_at')

    pending_contracts = PurchaseContract.objects.filter(
        approved_by__isnull=True,
        status=PurchaseContract.STATUS_PENDING,
    ).select_related('customer', 'vehicle', 'assigned_to').order_by('-contract_date')

    return render(request, 'leads/approval_list.html', {
        'pending_assessments': pending_assessments,
        'pending_contracts': pending_contracts,
    })


# ===========================================================================
# 新規 API
# ===========================================================================

@login_required
@require_POST
def promote_to_case(request, request_id):
    """査定申込 → 案件（Assessment）昇格 API"""
    req = get_object_or_404(CarAssessmentRequest, pk=request_id)

    try:
        _ = req.assessment
        return JsonResponse({'success': False, 'message': 'すでに案件に昇格済みです'}, status=400)
    except Assessment.DoesNotExist:
        pass

    if not req.customer or not req.vehicle:
        return JsonResponse({'success': False, 'message': '顧客・車両情報を先に登録してください'}, status=400)

    try:
        with transaction.atomic():
            assessment = Assessment.objects.create(
                assessment_request=req,
                customer=req.customer,
                vehicle=req.vehicle,
                assigned_to=req.assigned_to or request.user,
                assessment_datetime=req.reservation_datetime,
            )
            req.follow_status = CarAssessmentRequest.STATUS_PROMOTED
            req.save(update_fields=['follow_status', 'updated_at'])
    except Exception as e:
        logger.error(f'promote_to_case failed: {e}')
        return JsonResponse({'success': False, 'message': '案件昇格に失敗しました'}, status=500)

    return JsonResponse({
        'success': True,
        'message': '案件に昇格しました',
        'case_url': f'/sateiinfo/cases/{assessment.pk}/',
    })


@login_required
@require_POST
def approve_assessment(request, assessment_id):
    """査定承認 API"""
    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.can_approve) and not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': '承認権限がありません'}, status=403)

    assessment = get_object_or_404(Assessment, pk=assessment_id)
    try:
        payload = json.loads(request.body)
        action = payload.get('action')  # 'approve' or 'reject'
        reason = payload.get('reason', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if action == 'approve':
        assessment.approved_by = request.user
        assessment.approved_at = timezone.now()
        assessment.save(update_fields=['approved_by', 'approved_at', 'updated_at'])
        return JsonResponse({'success': True, 'message': '承認しました'})
    elif action == 'reject':
        assessment.approved_by = None
        assessment.cancel_reason = reason
        assessment.save(update_fields=['cancel_reason', 'updated_at'])
        return JsonResponse({'success': True, 'message': '差し戻しました'})

    return JsonResponse({'success': False, 'message': 'action が不正です'}, status=400)


@login_required
@require_POST
def approve_contract(request, contract_id):
    """契約承認 API"""
    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.can_approve) and not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': '承認権限がありません'}, status=403)

    contract = get_object_or_404(PurchaseContract, pk=contract_id)
    try:
        payload = json.loads(request.body)
        action = payload.get('action')
        reason = payload.get('reason', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if action == 'approve':
        contract.approved_by = request.user
        contract.approved_at = timezone.now()
        contract.status = PurchaseContract.STATUS_CONTRACTED
        contract.save(update_fields=['approved_by', 'approved_at', 'status', 'updated_at'])
        return JsonResponse({'success': True, 'message': '契約を承認しました'})
    elif action == 'reject':
        contract.cancel_reason = reason
        contract.save(update_fields=['cancel_reason', 'updated_at'])
        return JsonResponse({'success': True, 'message': '差し戻しました'})

    return JsonResponse({'success': False, 'message': 'action が不正です'}, status=400)


@login_required
@require_POST
def add_contact_history(request):
    """連絡履歴追加 API"""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    request_id = payload.get('assessment_request_id')
    method = payload.get('contact_method', 'phone')
    content = payload.get('content', '').strip()
    contacted_at_raw = payload.get('contacted_at', '')

    if not request_id or not content:
        return JsonResponse({'success': False, 'message': '必須項目が不足しています'}, status=400)

    req = get_object_or_404(CarAssessmentRequest, pk=request_id)

    contacted_at = timezone.now()
    if contacted_at_raw:
        try:
            contacted_at = timezone.make_aware(datetime.strptime(contacted_at_raw, '%Y-%m-%dT%H:%M'))
        except ValueError:
            pass

    history = ContactHistory.objects.create(
        assessment_request=req,
        customer=req.customer,
        recorded_by=request.user,
        contacted_at=contacted_at,
        contact_method=method,
        content=content,
    )

    return JsonResponse({
        'success': True,
        'message': '履歴を追加しました',
        'history': {
            'id': history.pk,
            'contacted_at': timezone.localtime(history.contacted_at).strftime('%Y-%m-%d %H:%M'),
            'contact_method': history.get_contact_method_display(),
            'content': history.content,
            'recorded_by': _current_user_display_name(request.user),
        }
    })
