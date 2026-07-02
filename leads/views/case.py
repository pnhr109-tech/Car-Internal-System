"""
views/case.py — 案件・商談フェーズ

画面ビュー:
  case_list, case_detail

API:
  update_assessment_info, update_vehicle_info, update_customer_info,
  save_bank_account, delete_bank_account, approve_assessment,
  add_contact_history, add_check_item, delete_check_item,
  add_advance_payment, delete_advance_payment,
  approve_advance_payment, update_required_docs
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
    AASaleImageUpload,
    AdvancePayment,
    Assessment,
    AssessmentCheckItem,
    AuctionVenue,
    CarAssessmentRequest,
    ContactHistory,
    ContractFileUpload,
    Customer,
    CustomerBankAccount,
    OtherFeeItem,
    OwnershipRelease,
    PurchaseContract,
    SalesProcess,
    Vehicle,
)
from .utils import (
    _current_user_display_name,
    _serialize_contract_file, _serialize_aa_image,
    _serialize_other_fee_item,
    _sync_document_done,
    ja_full_name,
)

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
            Q(case_number__icontains=q) |
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
        contract = PurchaseContract.objects.select_related(
            'manager1', 'manager2', 'approved_by', 'correction_approved_by'
        ).get(assessment=assessment)
    except PurchaseContract.DoesNotExist:
        contract = None

    histories     = assessment.assessment_request.contact_histories.select_related('recorded_by').order_by('-contacted_at')
    check_items     = assessment.check_items.all()
    documents       = contract.documents.select_related('document_type').all() if contract else []
    identity_docs   = contract.identity_documents.all() if contract else []
    contract_files_by_type = {}
    if contract:
        for f in contract.file_uploads.select_related('uploaded_by'):
            contract_files_by_type.setdefault(f.doc_type, []).append(_serialize_contract_file(f))
    bank_accounts   = assessment.customer.bank_accounts.all()
    primary_bank_account = bank_accounts.filter(is_primary=True).first() or bank_accounts.first()
    ownership_release = getattr(contract, 'ownership_release', None) if contract else None
    advance_payments  = contract.advance_payments.select_related('approved_by').all() if contract else []
    sales_process = getattr(contract, 'sales_process', None) if contract else None
    repair_flag   = contract.repair_flag if contract else False
    if sales_process:
        sp = sales_process
        step_available = {
            'intake':    sp.document_done,
            'repair':    sp.intake_done if repair_flag else None,  # None = 対象外
            'transport': (sp.repair_done if repair_flag else sp.intake_done),
            'listing':   sp.transport_done,
            'payment':   True,
        }
    else:
        step_available = {}
    aa_images_by_type = {}
    other_fee_items_list = []
    if sales_process:
        for img in sales_process.aa_images.select_related('uploaded_by'):
            aa_images_by_type.setdefault(img.image_type, []).append(_serialize_aa_image(img))
        other_fee_items_list = [
            _serialize_other_fee_item(item)
            for item in sales_process.other_fee_items.select_related('created_by')
        ]
    vehicle_images = assessment.vehicle.images.all()

    active_tab = request.GET.get('tab', 'assessment')
    profile    = getattr(request.user, 'profile', None)
    can_approve = profile.can_approve if profile else request.user.is_superuser

    from decimal import Decimal
    rating_choices = [Decimal(str(v / 10)) for v in range(10, 55, 5)]

    User      = get_user_model()
    all_users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
    approvers = User.objects.filter(is_active=True).filter(
        Q(is_superuser=True) |
        Q(profile__role__in=['sub_leader', 'manager', 'superuser'])
    ).distinct().order_by('last_name', 'first_name')

    contract_tax_rate = 10
    contract_total_payment = None
    if contract and contract.purchase_price_excl_tax and contract.purchase_price_excl_tax > 0:
        rate = round(float(contract.tax_amount / contract.purchase_price_excl_tax * 100))
        contract_tax_rate = rate if rate in (0, 8, 10) else 10
        contract_total_payment = (
            contract.purchase_price_excl_tax
            + contract.tax_amount
            + (contract.recycle_amount or 0)
        )

    editable_status_choices = Assessment.STATUS_CHOICES

    return render(request, 'leads/case_detail.html', {
        'assessment':                   assessment,
        'contract':                     contract,
        'contract_total_payment':       contract_total_payment,
        'histories':                    histories,
        'check_items':                  check_items,
        'documents':                    documents,
        'editable_status_choices':      editable_status_choices,
        'identity_docs':                identity_docs,
        'contract_files_by_type':       contract_files_by_type,
        'contract_doc_type_choices':    ContractFileUpload.DOC_TYPE_CHOICES,
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
        'approvers':                    approvers,
        'contract_tax_rate':            contract_tax_rate,
        'bank_institution_type_choices': CustomerBankAccount.INSTITUTION_TYPE_CHOICES,
        'primary_bank_account':          primary_bank_account,
        'bank_account_type_choices':     CustomerBankAccount.ACCOUNT_TYPE_CHOICES,
        'tristate_rows': [
            ('修復歴',                         contract.repair_history_flag        if contract else None),
            ('メーター戻し・改ざん等',         contract.meter_tampering            if contract else None),
            ('冠水車・雹害',                   contract.flood_hail_damage          if contract else None),
            ('故障箇所',                       contract.malfunction                if contract else None),
            ('駐車違反放置反則金未納',           contract.parking_violation          if contract else None),
            ('自動車税未納',                   contract.automobile_tax_unpaid      if contract else None),
            ('適格請求書発行事業者登録',         contract.qualified_invoice_registered if contract else None),
        ],
        'ownership_release':             ownership_release,
        'ownership_release_status_choices': OwnershipRelease.STATUS_CHOICES,
        'advance_payments':              advance_payments,
        'sales_process':                 sales_process,
        'step_available':                step_available,
        'aa_images_by_type':             aa_images_by_type,
        'aa_image_types':                AASaleImageUpload.IMAGE_TYPE_CHOICES,
        'other_fee_items':               other_fee_items_list,
        'other_fee_category_choices':    OtherFeeItem.CATEGORY_CHOICES,
        'disposition_choices':           SalesProcess.DISPOSITION_CHOICES,
        'auction_venues':                AuctionVenue.objects.all(),
        'required_doc_fields': [
            row for row in [
                ('inkan',    '印鑑証明', contract.required_inkan_count    if contract else 0, contract.inkan_received    if contract else False, contract.inkan_received_date    if contract else None),
                ('juminhyo', '住民票',   contract.required_juminhyo_count if contract else 0, contract.juminhyo_received if contract else False, contract.juminhyo_received_date if contract else None),
                ('jotohyo',  '除票',     contract.required_jotohyo_count  if contract else 0, contract.jotohyo_received  if contract else False, contract.jotohyo_received_date  if contract else None),
                ('ininjyo',  '委任状',   contract.required_ininjyo_count  if contract else 0, contract.ininjyo_received  if contract else False, contract.ininjyo_received_date  if contract else None),
                ('jotosho',  '譲渡書',   contract.required_jotosho_count  if contract else 0, contract.jotosho_received  if contract else False, contract.jotosho_received_date  if contract else None),
                ('kanpu',    '還付',     contract.required_kanpu_count    if contract else 0, contract.kanpu_received    if contract else False, contract.kanpu_received_date    if contract else None),
            ] if row[2] >= 1
        ],
    })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@login_required
@require_POST
def change_case_assignee(request, assessment_id):
    """案件担当者変更 API（管理者・承認権限者のみ）"""
    profile = getattr(request.user, 'profile', None)
    if not ((profile and profile.can_approve) or request.user.is_superuser):
        return JsonResponse({'success': False, 'message': '担当者変更には承認権限が必要です'}, status=403)

    assessment = get_object_or_404(Assessment, pk=assessment_id)
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        user_id = int(payload.get('user_id', 0))
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    User = get_user_model()
    new_assignee = get_object_or_404(User, pk=user_id, is_active=True)

    assessment.assigned_to = new_assignee
    assessment.save(update_fields=['assigned_to'])

    return JsonResponse({
        'success': True,
        'message': f'担当者を {ja_full_name(new_assignee)} に変更しました',
        'assigned_to_name': ja_full_name(new_assignee),
    })


@login_required
@require_POST
def change_appointment_getter(request, assessment_id):
    """商談取得者変更 API（管理者・承認権限者のみ）"""
    profile = getattr(request.user, 'profile', None)
    if not ((profile and profile.can_approve) or request.user.is_superuser):
        return JsonResponse({'success': False, 'message': '商談取得者変更には承認権限が必要です'}, status=403)

    assessment = get_object_or_404(Assessment, pk=assessment_id)
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        raw_id = payload.get('user_id', '')
        user_id = int(raw_id) if raw_id else None
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if user_id:
        User = get_user_model()
        new_getter = get_object_or_404(User, pk=user_id, is_active=True)
        assessment.appointment_getter = new_getter
        getter_name = ja_full_name(new_getter)
        msg = f'商談取得者を {getter_name} に変更しました'
    else:
        assessment.appointment_getter = None
        getter_name = '未設定'
        msg = '商談取得者を未設定にしました'

    assessment.save(update_fields=['appointment_getter'])

    return JsonResponse({
        'success': True,
        'message': msg,
        'appointment_getter_name': getter_name,
    })


@login_required
@require_POST
def update_assessment_info(request, assessment_id):
    """案件（査定）情報更新 API"""
    assessment = get_object_or_404(Assessment, pk=assessment_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    allowed_statuses = {s for s, _ in Assessment.STATUS_CHOICES} - {Assessment.STATUS_CONTRACTED}
    status = payload.get('status', '').strip()

    update_fields = ['updated_at']
    if status:
        # contracted → ステータス変更は専用 cancel-contracted API で行う
        if assessment.status == Assessment.STATUS_CONTRACTED:
            return JsonResponse({'success': False, 'message': '成約中の案件は成約キャンセル操作を使用してください'}, status=400)
        if status not in allowed_statuses:
            return JsonResponse({'success': False, 'message': 'ステータスが不正です'}, status=400)
        assessment.status = status
        update_fields.append('status')
        if status == Assessment.STATUS_MANAGED and not assessment.managed_at:
            assessment.managed_at = timezone.now()
            update_fields.append('managed_at')

    assessment_datetime_raw = payload.get('assessment_datetime', '')
    if assessment_datetime_raw:
        try:
            assessment.assessment_datetime = timezone.make_aware(
                datetime.strptime(assessment_datetime_raw, '%Y-%m-%dT%H:%M')
            )
            update_fields.append('assessment_datetime')
        except ValueError:
            pass

    for field in ('assessment_price', 'market_price_min', 'market_price_max'):
        val = payload.get(field)
        if val is not None and val != '':
            setattr(assessment, field, val)
        else:
            setattr(assessment, field, None)
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
        'displacement', 'chassis_number',
        'registration_number', 'passenger_count', 'body_type', 'drive_type',
    ]
    update_fields = ['updated_at']
    for f in str_fields:
        if f in payload:
            setattr(vehicle, f, payload[f])
            update_fields.append(f)

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
def import_from_assessment_system(request, assessment_id):
    """査定システムから車両情報を取り込む API"""
    from ..services.assessment_system_scraper import scrape_vehicle_data

    assessment = get_object_or_404(
        Assessment.objects.select_related('vehicle'),
        pk=assessment_id,
    )
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    assessment_system_id = payload.get('assessment_system_id', '').strip()
    if not assessment_system_id:
        return JsonResponse({'success': False, 'message': '査定システムIDを入力してください'}, status=400)

    try:
        data = scrape_vehicle_data(assessment_system_id)
    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=404)
    except Exception as e:
        logger.exception('査定システム取り込みエラー')
        return JsonResponse({'success': False, 'message': f'取り込みに失敗しました: {e}'}, status=500)

    # 車両情報を保存
    vehicle = assessment.vehicle
    for field, value in data['vehicle'].items():
        if field == 'inspection_expiry':
            vehicle.inspection_expiry = value
        elif value:
            setattr(vehicle, field, value)
    vehicle.updated_by = request.user
    vehicle.save()

    # Assessment に査定システム情報を保存
    assessment.assessment_system_id          = assessment_system_id
    assessment.assessment_system_imported_at = timezone.now()
    if data.get('assessment_price') is not None:
        assessment.assessment_price = data['assessment_price']
    if data.get('recycle_amount') is not None:
        assessment.assessment_system_recycle_amount = data['recycle_amount']
    if data.get('overall_rating') is not None:
        assessment.overall_rating = data['overall_rating']
    assessment.save(update_fields=[
        'assessment_system_id', 'assessment_system_imported_at',
        'assessment_price', 'assessment_system_recycle_amount', 'overall_rating', 'updated_at',
    ])

    return JsonResponse({
        'success':             True,
        'message':             '査定システムから車両情報を取り込みました',
        'assessment_price':    data.get('assessment_price'),
        'recycle_amount':      data.get('recycle_amount'),
        'overall_rating':      data.get('overall_rating'),
        'vehicle':             {
            k: str(v) if v is not None else ''
            for k, v in data['vehicle'].items()
            if k != 'inspection_expiry'
        } | {
            'inspection_expiry': data['vehicle']['inspection_expiry'].strftime('%Y-%m-%d')
            if data['vehicle'].get('inspection_expiry') else ''
        },
    })


@login_required
@require_POST
def save_assessment_system_id(request, assessment_id):
    """査定システムID保存 API（取り込みなし）"""
    assessment = get_object_or_404(Assessment, pk=assessment_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    assessment_system_id = payload.get('assessment_system_id', '').strip()
    assessment.assessment_system_id = assessment_system_id
    assessment.save(update_fields=['assessment_system_id', 'updated_at'])
    return JsonResponse({'success': True, 'assessment_system_id': assessment_system_id})


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
        'name', 'furigana', 'phone_number', 'email', 'postal_code', 'address',
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
def request_assessment_approval(request, assessment_id):
    """成約ステータス変更 + 承認申請 API（営業担当者が実行）"""
    assessment = get_object_or_404(Assessment, pk=assessment_id)

    try:
        payload     = json.loads(request.body)
        approver_id = payload.get('approver_id')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if not approver_id:
        return JsonResponse({'success': False, 'message': '承認者を選択してください'}, status=400)

    User     = get_user_model()
    approver = get_object_or_404(User, pk=approver_id, is_active=True)

    assessment.status                = Assessment.STATUS_CONTRACTED
    assessment.approval_requested_to = approver
    assessment.approval_requested_at = timezone.now()
    assessment.save(update_fields=['status', 'approval_requested_to', 'approval_requested_at', 'updated_at'])

    return JsonResponse({
        'success': True,
        'message': f'{ja_full_name(approver)} に承認申請しました',
        'approver_name': ja_full_name(approver),
    })


@login_required
@require_POST
def approve_assessment(request, assessment_id):
    """査定承認 API（承認申請先ユーザーのみ実行可）"""
    assessment = get_object_or_404(Assessment, pk=assessment_id)

    if assessment.status != Assessment.STATUS_CONTRACTED:
        return JsonResponse({'success': False, 'message': '成約ステータスの案件のみ承認できます'}, status=400)

    is_designated = (
        assessment.approval_requested_to_id is not None
        and assessment.approval_requested_to_id == request.user.pk
    )
    profile     = getattr(request.user, 'profile', None)
    can_approve = (profile and profile.can_approve) or request.user.is_superuser
    if not (is_designated or (can_approve and assessment.approval_requested_to_id is None)):
        return JsonResponse({'success': False, 'message': '承認権限がありません'}, status=403)

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
        assessment.cancel_reason             = reason
        assessment.approval_requested_to     = None
        assessment.approval_requested_at     = None
        assessment.save(update_fields=['cancel_reason', 'approval_requested_to', 'approval_requested_at', 'updated_at'])
        return JsonResponse({'success': True, 'message': '差し戻しました'})

    return JsonResponse({'success': False, 'message': 'action が不正です'}, status=400)


@login_required
@require_POST
def cancel_contracted_assessment(request, assessment_id):
    """成約キャンセル API — status を lost に変更し承認情報をクリアする"""
    assessment = get_object_or_404(Assessment, pk=assessment_id)

    if assessment.status != Assessment.STATUS_CONTRACTED:
        return JsonResponse({'success': False, 'message': '成約ステータスの案件のみキャンセルできます'}, status=400)

    assessment.status                = Assessment.STATUS_IN_PROGRESS
    assessment.cancelled_at          = timezone.now()
    assessment.approved_by           = None
    assessment.approved_at           = None
    assessment.approval_requested_to = None
    assessment.approval_requested_at = None
    assessment.save(update_fields=[
        'status', 'cancelled_at',
        'approved_by', 'approved_at',
        'approval_requested_to', 'approval_requested_at',
        'updated_at',
    ])
    return JsonResponse({'success': True, 'message': '成約をキャンセルしました（査定中に戻しました）'})


@login_required
def managed_release_list(request):
    """管理開放一覧 — 管理ステータスになってから4日以上経過した案件"""
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=4)
    qs = Assessment.objects.filter(
        status=Assessment.STATUS_MANAGED,
        managed_at__lte=cutoff,
    ).select_related(
        'assessment_request', 'customer', 'vehicle', 'assigned_to',
    ).order_by('managed_at')

    return render(request, 'leads/managed_release_list.html', {
        'assessments': qs,
        'editable_status_choices': [
            (s, l) for s, l in Assessment.STATUS_CHOICES
            if s != Assessment.STATUS_CONTRACTED
        ],
    })


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


# ---------------------------------------------------------------------------
# 先払い入金 API
# ---------------------------------------------------------------------------

@login_required
@require_POST
def add_advance_payment(request, contract_id):
    """先払い入金レコード追加 API"""
    contract = get_object_or_404(PurchaseContract, pk=contract_id)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    amount_raw = payload.get('expected_amount')
    if not amount_raw:
        return JsonResponse({'success': False, 'message': '入金予定額を入力してください'}, status=400)

    def _parse_date(val):
        if not val:
            return None
        try:
            return datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            return None

    try:
        ap = AdvancePayment.objects.create(
            contract=contract,
            expected_amount=amount_raw,
            payment_date=_parse_date(payload.get('payment_date')),
            status='unpaid',
        )
    except Exception as exc:
        logger.error(f'add_advance_payment failed: {exc}')
        return JsonResponse({'success': False, 'message': '追加に失敗しました'}, status=500)

    return JsonResponse({
        'success': True,
        'message': '先払い入金を追加しました',
        'id': ap.pk,
        'expected_amount': str(ap.expected_amount),
        'payment_date': ap.payment_date.strftime('%Y-%m-%d') if ap.payment_date else '',
        'status': ap.status,
        'status_display': ap.get_status_display(),
    })


@login_required
@require_POST
def delete_advance_payment(request, ap_id):
    """先払い入金レコード削除 API"""
    ap = get_object_or_404(AdvancePayment, pk=ap_id)
    if ap.approved_by:
        return JsonResponse({'success': False, 'message': '承認済の先払い入金は削除できません'}, status=400)
    ap.delete()
    return JsonResponse({'success': True, 'message': '先払い入金を削除しました'})


@login_required
@require_POST
def approve_advance_payment(request, ap_id):
    """先払い入金 承認 API（superuser 限定）"""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': 'この操作には社長権限が必要です'}, status=403)

    ap = get_object_or_404(AdvancePayment, pk=ap_id)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        payload = {}

    ap.approved_by = request.user
    ap.status = 'paid'
    if payload.get('payment_date'):
        try:
            ap.payment_date = datetime.strptime(payload['payment_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    ap.save()

    return JsonResponse({
        'success': True,
        'message': '先払い入金を承認しました',
        'approved_by_name': ja_full_name(request.user),
        'status_display': ap.get_status_display(),
    })


# ---------------------------------------------------------------------------
# 必要書類 受取確認 API
# ---------------------------------------------------------------------------

_REQUIRED_DOC_FIELDS = ['inkan', 'juminhyo', 'jotohyo', 'ininjyo', 'jotosho', 'kanpu']

@login_required
@require_POST
def update_required_docs(request, contract_id):
    """必要書類 受取フラグ更新 API。受領日はボタン押下時点の日付を自動設定する。"""
    contract = get_object_or_404(PurchaseContract, pk=contract_id)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    update_fields  = []
    updated_dates  = {}
    today          = timezone.localdate()
    for key in _REQUIRED_DOC_FIELDS:
        received_field = f'{key}_received'
        if received_field not in payload:
            continue
        is_received = bool(payload[received_field])
        date_field  = f'{key}_received_date'
        date_value  = today if is_received else None
        setattr(contract, received_field, is_received)
        setattr(contract, date_field, date_value)
        update_fields.extend([received_field, date_field])
        updated_dates[key] = date_value.isoformat() if date_value else None

    if update_fields:
        update_fields.append('updated_at')
        contract.save(update_fields=update_fields)

    # 書類ステップの自動完了 / 自動取消
    # contract.procedure_completed（書類受領・所有権解除・残債返済を含む）と一致させる。
    changed         = _sync_document_done(contract, request.user)
    auto_doc_done   = changed and contract.procedure_completed
    auto_doc_undone = changed and not contract.procedure_completed

    return JsonResponse({
        'success':         True,
        'message':         '受取状況を更新しました',
        'updated_dates':   updated_dates,
        'auto_doc_done':   auto_doc_done,
        'auto_doc_undone': auto_doc_undone,
    })
