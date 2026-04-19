"""
views/case.py — 案件・商談フェーズ

画面ビュー:
  case_list, case_detail

API:
  update_assessment_info, update_vehicle_info, update_customer_info,
  save_bank_account, delete_bank_account, approve_assessment,
  add_contact_history, add_check_item, delete_check_item
"""
import json
import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import (
    Assessment,
    AssessmentCheckItem,
    CarAssessmentRequest,
    ContactHistory,
    Customer,
    CustomerBankAccount,
    PurchaseContract,
    Vehicle,
)
from .utils import _current_user_display_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 画面ビュー
# ---------------------------------------------------------------------------

@login_required
def case_list(request):
    """案件一覧（S05）"""
    qs = Assessment.objects.select_related(
        'assessment_request', 'customer', 'vehicle', 'assigned_to', 'approved_by'
    ).order_by('-created_at')

    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_global_access:
        if profile.role == profile.ROLE_GENERAL:
            qs = qs.filter(assigned_to=request.user)
        else:
            store_users = profile.store.members.values_list('user_id', flat=True) if profile.store else []
            qs = qs.filter(assigned_to__in=store_users)

    q      = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if q:
        qs = qs.filter(
            Q(customer__name__icontains=q) | Q(customer__phone_number__icontains=q) |
            Q(vehicle__maker__icontains=q) | Q(vehicle__car_model__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'leads/case_list.html', {
        'page_obj':       page_obj,
        'q':              q,
        'status':         status,
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

    histories     = assessment.assessment_request.contact_histories.select_related('recorded_by').order_by('-contacted_at')
    check_items   = assessment.check_items.all()
    documents     = contract.documents.select_related('document_type').all() if contract else []
    identity_docs = contract.identity_documents.all() if contract else []
    bank_accounts = assessment.customer.bank_accounts.all()
    vehicle_images = assessment.vehicle.images.all()

    active_tab = request.GET.get('tab', 'assessment')
    profile    = getattr(request.user, 'profile', None)
    can_approve = profile.can_approve if profile else request.user.is_superuser

    from decimal import Decimal
    rating_choices = [Decimal(str(v / 10)) for v in range(10, 55, 5)]

    User      = get_user_model()
    all_users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')

    contract_tax_rate = 10
    if contract and contract.purchase_price_excl_tax and contract.purchase_price_excl_tax > 0:
        rate = round(float(contract.tax_amount / contract.purchase_price_excl_tax * 100))
        contract_tax_rate = rate if rate in (0, 8, 10) else 10

    return render(request, 'leads/case_detail.html', {
        'assessment':                   assessment,
        'contract':                     contract,
        'histories':                    histories,
        'check_items':                  check_items,
        'documents':                    documents,
        'identity_docs':                identity_docs,
        'bank_accounts':                bank_accounts,
        'vehicle_images':               vehicle_images,
        'active_tab':                   active_tab,
        'can_approve':                  can_approve,
        'assessment_status_choices':    Assessment.STATUS_CHOICES,
        'contract_status_choices':      PurchaseContract.STATUS_CHOICES if contract else [],
        'contact_method_choices':       ContactHistory.METHOD_CHOICES,
        'check_type_choices':           AssessmentCheckItem.CHECK_TYPE_CHOICES,
        'rating_choices':               rating_choices,
        'all_users':                    all_users,
        'contract_tax_rate':            contract_tax_rate,
        'transmission_choices':         Vehicle.TRANSMISSION_CHOICES,
        'fuel_type_choices':            Vehicle.FUEL_TYPE_CHOICES,
        'bank_institution_type_choices': CustomerBankAccount.INSTITUTION_TYPE_CHOICES,
    })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@login_required
@require_POST
def update_assessment_info(request, assessment_id):
    """案件（査定）情報更新 API"""
    assessment = get_object_or_404(Assessment, pk=assessment_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    allowed_statuses = {s for s, _ in Assessment.STATUS_CHOICES}
    status = payload.get('status', '').strip()
    if status and status not in allowed_statuses:
        return JsonResponse({'success': False, 'message': 'ステータスが不正です'}, status=400)

    update_fields = ['updated_at']
    if status:
        assessment.status = status
        update_fields.append('status')

    assessment_datetime_raw = payload.get('assessment_datetime', '')
    if assessment_datetime_raw:
        try:
            assessment.assessment_datetime = timezone.make_aware(
                datetime.strptime(assessment_datetime_raw, '%Y-%m-%dT%H:%M')
            )
            update_fields.append('assessment_datetime')
        except ValueError:
            pass

    for field in ('assessment_price', 'market_price'):
        val = payload.get(field)
        if val is not None and val != '':
            setattr(assessment, field, val)
            update_fields.append(field)

    overall_rating = payload.get('overall_rating')
    if overall_rating is not None and overall_rating != '':
        assessment.overall_rating = float(overall_rating)
        update_fields.append('overall_rating')

    remarks = payload.get('remarks')
    if remarks is not None:
        assessment.remarks = remarks
        update_fields.append('remarks')

    assessment.save(update_fields=list(set(update_fields)))
    return JsonResponse({'success': True, 'message': '案件情報を更新しました'})


@login_required
@require_POST
def update_vehicle_info(request, assessment_id):
    """車両詳細情報更新 API"""
    assessment = get_object_or_404(Assessment.objects.select_related('vehicle'), pk=assessment_id)
    vehicle    = assessment.vehicle
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    str_fields = [
        'maker', 'car_model', 'year', 'mileage', 'grade', 'color',
        'displacement', 'model_type', 'fuel_type', 'chassis_number', 'transmission_type',
        'registration_number', 'passenger_count', 'body_type', 'drive_type',
    ]
    update_fields = ['updated_at']
    for f in str_fields:
        if f in payload:
            setattr(vehicle, f, payload[f])
            update_fields.append(f)

    if 'repair_history_flag' in payload:
        val = payload['repair_history_flag']
        vehicle.repair_history_flag = None if val is None else bool(val)
        update_fields.append('repair_history_flag')

    if 'inspection_expiry' in payload:
        raw = payload['inspection_expiry']
        vehicle.inspection_expiry = None
        if raw:
            try:
                vehicle.inspection_expiry = datetime.strptime(raw, '%Y-%m-%d').date()
            except ValueError:
                pass
        update_fields.append('inspection_expiry')

    vehicle.updated_by = request.user
    update_fields.append('updated_by')
    vehicle.save(update_fields=list(set(update_fields)))
    return JsonResponse({'success': True, 'message': '車両情報を更新しました'})


@login_required
@require_POST
def update_customer_info(request, assessment_id):
    """顧客詳細情報更新 API（案件ページから）"""
    assessment = get_object_or_404(Assessment.objects.select_related('customer'), pk=assessment_id)
    customer   = assessment.customer
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    str_fields = [
        'name', 'phone_number', 'email', 'postal_code', 'address',
        'occupation', 'gender', 'family_structure', 'license_number',
    ]
    update_fields = ['updated_at']
    for f in str_fields:
        if f in payload:
            setattr(customer, f, payload[f])
            update_fields.append(f)

    if 'age' in payload:
        try:
            customer.age = int(payload['age']) if payload['age'] else None
        except (ValueError, TypeError):
            pass
        update_fields.append('age')

    if 'birth_date' in payload:
        raw = payload['birth_date']
        customer.birth_date = None
        if raw:
            try:
                customer.birth_date = datetime.strptime(raw, '%Y-%m-%d').date()
            except ValueError:
                pass
        update_fields.append('birth_date')

    customer.updated_by = request.user
    update_fields.append('updated_by')
    customer.save(update_fields=list(set(update_fields)))
    return JsonResponse({'success': True, 'message': '顧客情報を更新しました'})


@login_required
@require_POST
def save_bank_account(request, assessment_id):
    """口座情報追加・更新 API（案件ページから）"""
    assessment = get_object_or_404(Assessment.objects.select_related('customer'), pk=assessment_id)
    customer   = assessment.customer
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    bank_name             = payload.get('bank_name', '').strip()
    branch_name           = payload.get('branch_name', '').strip()
    bank_institution_type = payload.get('bank_institution_type', 'bank').strip()
    account_type          = payload.get('account_type', '普通').strip()
    account_number        = payload.get('account_number', '').strip()
    account_holder        = payload.get('account_holder', '').strip()
    is_primary            = bool(payload.get('is_primary', False))
    account_id            = payload.get('account_id')

    if not bank_name or not account_number or not account_holder:
        return JsonResponse({'success': False, 'message': '銀行名・口座番号・名義は必須です'}, status=400)

    with transaction.atomic():
        if is_primary:
            CustomerBankAccount.objects.filter(customer=customer).update(is_primary=False)
        if account_id:
            acc = get_object_or_404(CustomerBankAccount, pk=account_id, customer=customer)
            acc.bank_name             = bank_name
            acc.branch_name           = branch_name
            acc.bank_institution_type = bank_institution_type
            acc.account_type          = account_type
            acc.account_number        = account_number
            acc.account_holder        = account_holder
            acc.is_primary            = is_primary
            acc.updated_by            = request.user
            acc.save()
        else:
            acc = CustomerBankAccount.objects.create(
                customer=customer,
                bank_name=bank_name,
                branch_name=branch_name,
                bank_institution_type=bank_institution_type,
                account_type=account_type,
                account_number=account_number,
                account_holder=account_holder,
                is_primary=is_primary,
                updated_by=request.user,
            )

    return JsonResponse({'success': True, 'message': '口座情報を保存しました', 'account_id': acc.pk})


@login_required
@require_POST
def delete_bank_account(request, account_id):
    """口座情報削除 API（案件ページから）"""
    acc = get_object_or_404(CustomerBankAccount, pk=account_id)
    acc.delete()
    return JsonResponse({'success': True, 'message': '口座情報を削除しました'})


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
        action  = payload.get('action')
        reason  = payload.get('reason', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if action == 'approve':
        assessment.approved_by = request.user
        assessment.approved_at = timezone.now()
        assessment.save(update_fields=['approved_by', 'approved_at', 'updated_at'])
        return JsonResponse({'success': True, 'message': '承認しました'})
    elif action == 'reject':
        assessment.cancel_reason = reason
        assessment.save(update_fields=['cancel_reason', 'updated_at'])
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

    request_id      = payload.get('assessment_request_id')
    method          = payload.get('contact_method', 'phone')
    content         = payload.get('content', '').strip()
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
            'id':             history.pk,
            'contacted_at':   timezone.localtime(history.contacted_at).strftime('%Y-%m-%d %H:%M'),
            'contact_method': history.get_contact_method_display(),
            'content':        history.content,
            'recorded_by':    _current_user_display_name(request.user),
        },
    })


@login_required
@require_POST
def add_check_item(request, assessment_id):
    """査定チェック項目追加 API"""
    assessment = get_object_or_404(Assessment, pk=assessment_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    check_type  = payload.get('check_type', '').strip()
    description = payload.get('description', '').strip()

    if check_type not in {t for t, _ in AssessmentCheckItem.CHECK_TYPE_CHOICES}:
        return JsonResponse({'success': False, 'message': 'チェック種別が不正です'}, status=400)

    item = AssessmentCheckItem.objects.create(
        assessment=assessment,
        check_type=check_type,
        description=description,
    )
    return JsonResponse({
        'success': True,
        'message': 'チェック項目を追加しました',
        'item': {
            'id':                item.pk,
            'check_type':        item.check_type,
            'check_type_display': item.get_check_type_display(),
            'description':       item.description,
        },
    })


@login_required
@require_POST
def delete_check_item(request, item_id):
    """査定チェック項目削除 API"""
    item = get_object_or_404(AssessmentCheckItem, pk=item_id)
    item.delete()
    return JsonResponse({'success': True, 'message': 'チェック項目を削除しました'})
