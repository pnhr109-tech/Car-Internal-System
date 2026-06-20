"""
views/assessment.py — 査定申込フェーズ（アポイント）

画面ビュー:
  assessment_list, assessment_detail, assessment_create, assessment_edit

API:
  get_assessments, check_new_assessments, get_latest_assessment_id,
  get_assessment_detail, claim_assessment_owner,
  increment_assessment_call_count, update_assessment_follow_status,
  promote_to_case
"""
import json
import logging
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Max, Q, Subquery, OuterRef, CharField, IntegerField
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import (
    Assessment,
    CarAssessmentRequest,
    ContactHistory,
    Customer,
    PurchaseContract,
    Vehicle,
)
from .utils import (
    _current_user_display_name,
    _generate_application_number,
    generate_case_number,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------

def _auto_create_assessment_for_request(req, user):
    """商談予定ステータス遷移時に Assessment を自動生成する（既存の場合はスキップ）。"""
    try:
        _ = req.assessment
        return
    except Assessment.DoesNotExist:
        pass

    if not req.customer:
        customer = Customer.objects.create(
            name=req.customer_name,
            phone_number=req.phone_number,
            email=req.email or '',
            postal_code=req.postal_code or '',
            address=req.address or '',
            updated_by=user,
        )
        req.customer = customer
        req.save(update_fields=['customer', 'updated_at'])

    if not req.vehicle:
        vehicle = Vehicle.objects.create(
            maker=req.maker or '',
            car_model=req.car_model or '',
            year=req.year or '',
            mileage=req.mileage or '',
            updated_by=user,
        )
        req.vehicle = vehicle
        req.save(update_fields=['vehicle', 'updated_at'])

    Assessment.objects.create(
        assessment_request=req,
        customer=req.customer,
        vehicle=req.vehicle,
        assigned_to=req.assigned_to or user,
        assessment_datetime=req.reservation_datetime,
        case_number=generate_case_number(),
    )


# ---------------------------------------------------------------------------
# 画面ビュー
# ---------------------------------------------------------------------------

_MODAL_EXCLUDED_STATUSES = {
    CarAssessmentRequest.STATUS_PROMOTED,  # 商談昇格済（案件昇格フローで自動設定）
    CarAssessmentRequest.STATUS_CLOSED,    # 成約（承認フローで設定）
}

@login_required
def assessment_list(request):
    """査定申込一覧"""
    return render(request, 'leads/assessment_list.html', {
        'current_user_display_name': _current_user_display_name(request.user),
        'follow_status_choices': [
            c[0] for c in CarAssessmentRequest.FOLLOW_STATUS_CHOICES
            if c[0] not in _MODAL_EXCLUDED_STATUSES
        ],
        'channel_choices': CarAssessmentRequest.CHANNEL_CHOICES,
    })


@login_required
def assessment_detail(request, pk):
    """査定申込詳細・変更（S02）"""
    req = get_object_or_404(CarAssessmentRequest, pk=pk)
    histories = req.contact_histories.select_related('recorded_by').order_by('-contacted_at')
    try:
        linked_assessment = req.assessment
        has_assessment = True
    except Assessment.DoesNotExist:
        linked_assessment = None
        has_assessment = False
    can_promote = (
        req.follow_status == CarAssessmentRequest.STATUS_APPOINTMENT
        and not has_assessment
    )

    return render(request, 'leads/assessment_detail.html', {
        'req': req,
        'histories': histories,
        'can_promote': can_promote,
        'linked_assessment': linked_assessment,
        'follow_status_choices': [
            c for c in CarAssessmentRequest.FOLLOW_STATUS_CHOICES
            if c[0] not in _MODAL_EXCLUDED_STATUSES
        ],
        'channel_choices': CarAssessmentRequest.CHANNEL_CHOICES,
        'contact_method_choices': ContactHistory.METHOD_CHOICES,
    })


@login_required
def assessment_create(request):
    """査定申込手動入力（S03）"""
    if request.method == 'POST':
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

        mileage_raw = request.POST.get('mileage', '').strip()
        mileage_val = f'{mileage_raw}万Km' if mileage_raw else ''
        vehicle = Vehicle.objects.create(
            maker=request.POST.get('maker', ''),
            car_model=request.POST.get('car_model', ''),
            year=request.POST.get('year', ''),
            mileage=mileage_val,
            updated_by=request.user,
        )

        channel_type = request.POST.get('channel_type', CarAssessmentRequest.CHANNEL_HP)
        today = timezone.localdate(timezone.now())
        application_number = _generate_application_number(channel_type, today)

        reservation_dt = None
        reservation_raw = request.POST.get('reservation_datetime', '')
        if reservation_raw:
            try:
                reservation_dt = timezone.make_aware(
                    datetime.strptime(reservation_raw, '%Y-%m-%dT%H:%M')
                )
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

    customer_search = request.GET.get('customer_search', '').strip()
    found_customers = []
    if customer_search:
        found_customers = Customer.objects.filter(
            Q(name__icontains=customer_search) | Q(phone_number__icontains=customer_search)
        )[:10]

    current_year = timezone.localdate(timezone.now()).year
    year_choices = [f'{y}年' for y in range(current_year + 1, 1969, -1)]
    manual_channel_choices = [
        (val, label) for val, label in CarAssessmentRequest.CHANNEL_CHOICES
        if val != CarAssessmentRequest.CHANNEL_MANUAL
    ]

    return render(request, 'leads/assessment_create.html', {
        'channel_choices': manual_channel_choices,
        'customer_search': customer_search,
        'found_customers': found_customers,
        'year_choices': year_choices,
    })


@login_required
def assessment_edit(request, pk):
    """査定申込編集"""
    req = get_object_or_404(CarAssessmentRequest, pk=pk)

    if request.method == 'POST':
        mileage_raw = request.POST.get('mileage', '').strip()
        mileage_val = f'{mileage_raw}万Km' if mileage_raw else ''

        reservation_dt = req.reservation_datetime
        reservation_raw = request.POST.get('reservation_datetime', '')
        if reservation_raw:
            try:
                reservation_dt = timezone.make_aware(
                    datetime.strptime(reservation_raw, '%Y-%m-%dT%H:%M')
                )
            except ValueError:
                pass
        elif reservation_raw == '':
            reservation_dt = None

        req.channel_type       = request.POST.get('channel_type', req.channel_type)
        req.referral_name      = request.POST.get('referral_name', '')
        req.reservation_datetime = reservation_dt
        req.desired_sale_timing = request.POST.get('desired_sale_timing', '')
        req.customer_name      = request.POST.get('customer_name', req.customer_name)
        req.phone_number       = request.POST.get('phone_number', req.phone_number)
        req.email              = request.POST.get('email', req.email)
        req.postal_code        = request.POST.get('postal_code', req.postal_code)
        req.address            = request.POST.get('address', req.address)
        req.maker              = request.POST.get('maker', req.maker)
        req.car_model          = request.POST.get('car_model', req.car_model)
        req.year               = request.POST.get('year', req.year)
        req.mileage            = mileage_val
        req.sales_note         = request.POST.get('sales_note', req.sales_note)
        req.save()

        messages.success(request, '査定申込を更新しました')
        return redirect('leads:assessment_detail', pk=req.pk)

    current_year = timezone.localdate(timezone.now()).year
    year_choices = [f'{y}年' for y in range(current_year + 1, 1969, -1)]
    mileage_num = req.mileage.replace('万Km', '').replace('万km', '').strip() if req.mileage else ''
    reservation_str = (
        timezone.localtime(req.reservation_datetime).strftime('%Y-%m-%dT%H:%M')
        if req.reservation_datetime else ''
    )
    manual_channel_choices = [
        (val, label) for val, label in CarAssessmentRequest.CHANNEL_CHOICES
        if val != CarAssessmentRequest.CHANNEL_MANUAL
    ]

    return render(request, 'leads/assessment_edit.html', {
        'req': req,
        'channel_choices': manual_channel_choices,
        'year_choices': year_choices,
        'mileage_num': mileage_num,
        'reservation_str': reservation_str,
    })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@login_required
def get_assessments(request):
    """査定申込データ一覧取得 API（検索・ページネーション対応）"""
    application_number = request.GET.get('application_number', '').strip()
    customer_name      = request.GET.get('customer_name', '').strip()
    phone_number       = request.GET.get('phone_number', '').strip()
    maker              = request.GET.get('maker', '').strip()
    car_model          = request.GET.get('car_model', '').strip()
    address            = request.GET.get('address', '').strip()
    external_id        = request.GET.get('external_id', '').strip()
    date_from          = request.GET.get('date_from', '').strip()
    date_to            = request.GET.get('date_to', '').strip()
    page               = int(request.GET.get('page', 1))
    per_page           = int(request.GET.get('per_page', 100))

    has_search = bool(
        application_number or customer_name or phone_number or maker
        or car_model or address or external_id or date_from or date_to
    )

    case_status_subq = Assessment.objects.filter(
        assessment_request_id=OuterRef('pk')
    ).values('status')[:1]
    case_id_subq = Assessment.objects.filter(
        assessment_request_id=OuterRef('pk')
    ).values('pk')[:1]

    queryset = CarAssessmentRequest.objects.annotate(
        case_status=Subquery(case_status_subq, output_field=CharField()),
        case_id=Subquery(case_id_subq, output_field=IntegerField()),
    ).order_by('-application_datetime')

    if not has_search:
        queryset = queryset[:100]

    if application_number:
        queryset = queryset.filter(application_number=application_number)
    if customer_name:
        queryset = queryset.filter(customer_name__icontains=customer_name)
    if phone_number:
        queryset = queryset.filter(phone_number__icontains=phone_number)
    if maker:
        queryset = queryset.filter(maker__icontains=maker)
    if car_model:
        queryset = queryset.filter(car_model__icontains=car_model)
    if address:
        queryset = queryset.filter(address__icontains=address)
    if external_id:
        queryset = queryset.filter(external_service_id__icontains=external_id)
    if date_from:
        try:
            queryset = queryset.filter(
                application_datetime__gte=datetime.strptime(date_from, '%Y-%m-%d')
            )
        except ValueError:
            pass
    if date_to:
        try:
            queryset = queryset.filter(
                application_datetime__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59
                )
            )
        except ValueError:
            pass

    total_count = queryset.count() if has_search else min(queryset.count(), 100)
    paginator   = Paginator(queryset, per_page)
    page_obj    = paginator.get_page(page)

    def _fmt(dt, pattern):
        return timezone.localtime(dt).strftime(pattern) if dt else ''

    data = [
        {
            'id':                   row['id'],
            'application_number':   row['application_number'],
            'external_service_id':  row['external_service_id'] or '',
            'application_datetime': _fmt(row.get('application_datetime'), '%Y-%m-%d %H:%M'),
            'desired_sale_timing':  row['desired_sale_timing'],
            'maker':                row['maker'],
            'car_model':            row['car_model'],
            'year':                 row['year'],
            'mileage':              row['mileage'],
            'customer_name':        row['customer_name'],
            'phone_number':         row['phone_number'],
            'call_count':           row['call_count'],
            'postal_code':          row['postal_code'],
            'address':              row['address'],
            'email':                row['email'],
            'sales_owner_name':     row['sales_owner_name'],
            'sales_assigned_at':    _fmt(row.get('sales_assigned_at'), '%Y-%m-%d %H:%M'),
            'follow_status':        row['follow_status'],
            'sales_note':           row['sales_note'],
            'reservation_datetime': _fmt(row.get('reservation_datetime'), '%Y-%m-%dT%H:%M'),
            'status_updated_at':    _fmt(row.get('status_updated_at'), '%Y-%m-%d %H:%M'),
            'status_updated_by':    row['status_updated_by'],
            'created_at':           _fmt(row.get('created_at'), '%Y-%m-%d %H:%M:%S'),
            'case_status':          row.get('case_status') or '',
            'case_id':              row.get('case_id'),
        }
        for row in page_obj.object_list.values(
            'id', 'application_number', 'external_service_id', 'application_datetime',
            'desired_sale_timing', 'maker', 'car_model', 'year', 'mileage',
            'customer_name', 'phone_number', 'call_count', 'postal_code',
            'case_status', 'case_id', 'address', 'email', 'sales_owner_name',
            'sales_assigned_at', 'follow_status', 'sales_note',
            'reservation_datetime', 'status_updated_at', 'status_updated_by', 'created_at',
        )
    ]

    return JsonResponse({
        'success':      True,
        'total_count':  total_count,
        'page':         page_obj.number,
        'total_pages':  paginator.num_pages,
        'per_page':     per_page,
        'count':        len(data),
        'has_previous': page_obj.has_previous(),
        'has_next':     page_obj.has_next(),
        'data':         data,
    })


@login_required
def check_new_assessments(request):
    """新規レコードチェック API（通知ポーリング用）"""
    try:
        last_id = int(request.GET.get('last_id', 0))
    except ValueError:
        last_id = 0

    new_records = CarAssessmentRequest.objects.filter(id__gt=last_id).order_by('-id').values(
        'id', 'application_number', 'application_datetime', 'customer_name', 'maker', 'car_model',
    )

    data = [
        {
            'id':                   row['id'],
            'application_number':   row['application_number'],
            'application_datetime': (
                timezone.localtime(row['application_datetime']).strftime('%Y-%m-%d %H:%M')
                if row.get('application_datetime') else ''
            ),
            'customer_name': row['customer_name'],
            'maker':         row['maker'],
            'car_model':     row['car_model'],
        }
        for row in new_records
    ]

    return JsonResponse({'success': True, 'has_new': bool(data), 'count': len(data), 'data': data})


@login_required
def get_latest_assessment_id(request):
    """最新申込 ID 取得 API（通知ポーリング初期化用）"""
    latest_id = CarAssessmentRequest.objects.aggregate(max_id=Max('id')).get('max_id') or 0
    return JsonResponse({'success': True, 'latest_id': latest_id})


@login_required
def get_assessment_detail(request, request_id):
    """査定申込詳細 API"""
    target = CarAssessmentRequest.objects.filter(id=request_id).values(
        'id', 'application_number', 'application_datetime', 'desired_sale_timing',
        'maker', 'car_model', 'year', 'mileage', 'customer_name', 'phone_number',
        'call_count', 'postal_code', 'address', 'email', 'sales_owner_name',
        'sales_assigned_at', 'follow_status', 'sales_note',
        'status_updated_at', 'status_updated_by', 'created_at',
    ).first()

    if not target:
        return JsonResponse({'success': False, 'message': '対象データが存在しません'}, status=404)

    def _fmt(dt, pattern):
        return timezone.localtime(dt).strftime(pattern) if dt else ''

    data = {
        **target,
        'application_datetime': _fmt(target.get('application_datetime'), '%Y-%m-%d %H:%M'),
        'sales_assigned_at':    _fmt(target.get('sales_assigned_at'), '%Y-%m-%d %H:%M'),
        'status_updated_at':    _fmt(target.get('status_updated_at'), '%Y-%m-%d %H:%M'),
        'created_at':           _fmt(target.get('created_at'), '%Y-%m-%d %H:%M:%S'),
    }
    return JsonResponse({'success': True, 'data': data})


@login_required
@require_POST
def claim_assessment_owner(request, request_id):
    """担当営業挙手 API"""
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
                return JsonResponse({'success': False, 'message': '未対応の案件のみ挙手できます'}, status=400)

            now = timezone.now()
            target.sales_owner_name  = sales_name
            target.sales_assigned_at = now
            target.status_updated_by = sales_name
            target.status_updated_at = now
            target.save(update_fields=[
                'sales_owner_name', 'sales_assigned_at',
                'status_updated_by', 'status_updated_at', 'updated_at',
            ])
    except Exception as exc:
        logger.error(f'claim_assessment_owner failed: request_id={request_id}, error={exc}')
        return JsonResponse({'success': False, 'message': '担当営業の登録に失敗しました'}, status=500)

    return JsonResponse({'success': True, 'message': '担当営業として登録しました', 'sales_owner_name': sales_name})


@login_required
@require_POST
def increment_assessment_call_count(request, request_id):
    """通話数インクリメント API"""
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

    return JsonResponse({'success': True, 'call_count': target.call_count})


@login_required
@require_POST
def update_assessment_follow_status(request, request_id):
    """対応ステータス更新 API"""
    sales_name = _current_user_display_name(request.user)
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    follow_status        = str(payload.get('follow_status', '')).strip()
    sales_note           = str(payload.get('sales_note', '')).strip()
    reservation_datetime_raw = str(payload.get('reservation_datetime', '')).strip()
    allowed_statuses = {c[0] for c in CarAssessmentRequest.FOLLOW_STATUS_CHOICES}

    if follow_status not in allowed_statuses:
        return JsonResponse({'success': False, 'message': '対応ステータスが不正です'}, status=400)

    if follow_status == CarAssessmentRequest.STATUS_APPOINTMENT and not reservation_datetime_raw:
        return JsonResponse({'success': False, 'message': '商談予定日時を入力してください'}, status=400)

    reservation_dt = None
    if reservation_datetime_raw:
        try:
            reservation_dt = timezone.make_aware(
                datetime.strptime(reservation_datetime_raw, '%Y-%m-%dT%H:%M')
            )
        except ValueError:
            return JsonResponse({'success': False, 'message': '商談予定日時の形式が不正です'}, status=400)

    # 担当確定を伴うステータス
    _ASSIGN_STATUSES = {
        CarAssessmentRequest.STATUS_APPOINTMENT,  # 商談予定
        CarAssessmentRequest.STATUS_CALLBACK,     # 再コール予定
    }

    try:
        with transaction.atomic():
            target = CarAssessmentRequest.objects.select_for_update().filter(id=request_id).first()
            if not target:
                return JsonResponse({'success': False, 'message': '対象データが存在しません'}, status=404)

            old_follow_status = target.follow_status

            # 商談予定 → 他ステータスへの変更: 自動生成した Assessment を削除
            if (old_follow_status == CarAssessmentRequest.STATUS_APPOINTMENT
                    and follow_status != CarAssessmentRequest.STATUS_APPOINTMENT):
                try:
                    existing_assessment = target.assessment
                    has_contract = PurchaseContract.objects.filter(
                        assessment=existing_assessment,
                    ).exclude(status=PurchaseContract.STATUS_CANCELLED).exists()
                    if existing_assessment.status == Assessment.STATUS_CONTRACTED or has_contract:
                        return JsonResponse(
                            {'success': False, 'message': '成約済みまたは契約書が作成されているため、商談予定から戻せません'},
                            status=400,
                        )
                    existing_assessment.delete()
                except Assessment.DoesNotExist:
                    pass

            update_fields = ['follow_status', 'sales_note', 'status_updated_by', 'status_updated_at', 'updated_at']

            if reservation_dt is not None:
                target.reservation_datetime = reservation_dt
                update_fields.append('reservation_datetime')

            if follow_status in _ASSIGN_STATUSES:
                # 商談予定・再コール予定 → 担当自動確定。他担当者は変更不可
                if not target.sales_owner_name:
                    target.sales_owner_name  = sales_name
                    target.sales_assigned_at = timezone.now()
                    target.assigned_to       = request.user
                    update_fields += ['sales_owner_name', 'sales_assigned_at', 'assigned_to']
                elif target.sales_owner_name != sales_name:
                    return JsonResponse(
                        {'success': False, 'message': f'担当営業（{target.sales_owner_name}）のみ更新できます'},
                        status=403,
                    )
            else:
                # 担当確定不要ステータス（不通・即ぷ・見送りなど）
                if target.sales_owner_name and target.sales_owner_name != sales_name:
                    # 他人が担当確定している案件には触れない
                    return JsonResponse(
                        {'success': False, 'message': f'担当営業（{target.sales_owner_name}）のみ更新できます'},
                        status=403,
                    )
                elif target.sales_owner_name == sales_name:
                    # 自分が担当のままステータスを戻す → 担当クリア
                    target.sales_owner_name  = ''
                    target.sales_assigned_at = None
                    target.assigned_to       = None
                    update_fields += ['sales_owner_name', 'sales_assigned_at', 'assigned_to']
                # 担当なし → 誰でも更新可、担当は変わらず

            now = timezone.now()
            target.follow_status     = follow_status
            target.sales_note        = sales_note
            target.status_updated_by = sales_name
            target.status_updated_at = now
            target.save(update_fields=update_fields)

            # 商談予定へ遷移したら Assessment を自動生成
            if follow_status == CarAssessmentRequest.STATUS_APPOINTMENT:
                _auto_create_assessment_for_request(target, request.user)

    except Exception as exc:
        logger.error(f'update_assessment_follow_status failed: request_id={request_id}, error={exc}')
        return JsonResponse({'success': False, 'message': 'ステータス更新に失敗しました'}, status=500)

    return JsonResponse({'success': True, 'message': 'ステータスを更新しました'})


@login_required
@require_POST
def promote_to_case(request, request_id):
    """査定申込 → 案件 昇格 API（手動フォールバック）"""
    req = get_object_or_404(CarAssessmentRequest, pk=request_id)

    try:
        _ = req.assessment
        return JsonResponse({'success': False, 'message': 'すでに案件に昇格済みです'}, status=400)
    except Assessment.DoesNotExist:
        pass

    try:
        with transaction.atomic():
            # スクレイパー経由の申込は customer/vehicle FK が未設定のため自動生成
            if not req.customer:
                customer = Customer.objects.create(
                    name=req.customer_name,
                    phone_number=req.phone_number,
                    email=req.email or '',
                    postal_code=req.postal_code or '',
                    address=req.address or '',
                    updated_by=request.user,
                )
                req.customer = customer

            if not req.vehicle:
                vehicle = Vehicle.objects.create(
                    maker=req.maker or '',
                    car_model=req.car_model or '',
                    year=req.year or '',
                    mileage=req.mileage or '',
                    updated_by=request.user,
                )
                req.vehicle = vehicle

            # assigned_to: 申込の担当者を優先。未設定の場合は sales_owner_name からユーザーを検索
            assigned_user = req.assigned_to
            if not assigned_user and req.sales_owner_name:
                from django.contrib.auth import get_user_model
                _User = get_user_model()
                name_parts = req.sales_owner_name.strip().split()
                if len(name_parts) >= 2:
                    assigned_user = _User.objects.filter(
                        last_name=name_parts[0], first_name=name_parts[1]
                    ).first()
            assigned_user = assigned_user or request.user

            assessment = Assessment.objects.create(
                assessment_request=req,
                customer=req.customer,
                vehicle=req.vehicle,
                assigned_to=assigned_user,
                assessment_datetime=req.reservation_datetime,
                case_number=generate_case_number(),
            )
            req.follow_status = CarAssessmentRequest.STATUS_PROMOTED
            req.save(update_fields=['follow_status', 'customer', 'vehicle', 'updated_at'])
    except Exception as exc:
        logger.error(f'promote_to_case failed: {exc}')
        return JsonResponse({'success': False, 'message': '案件昇格に失敗しました'}, status=500)

    return JsonResponse({
        'success':  True,
        'message':  '案件に昇格しました',
        'case_url': f'/sateiinfo/cases/{assessment.pk}/',
    })
