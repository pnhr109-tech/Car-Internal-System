"""
views/contract.py — 契約・承認フェーズ

画面ビュー:
  contract_list, contract_print, approval_list

API:
  create_contract, update_contract, approve_contract,
  approve_correction
"""
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Store, UserProfile
from ..models import (
    AASaleImageUpload,
    Assessment,
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
    _parse_tristate, _parse_date,
    _sync_customer_from_contract,
    _serialize_contract_file, _serialize_aa_image,
    _serialize_other_fee_item, _sync_other_fee,
    _sync_document_done,
    ja_full_name,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 画面ビュー
# ---------------------------------------------------------------------------

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

    q      = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if q:
        qs = qs.filter(Q(customer__name__icontains=q) | Q(customer__phone_number__icontains=q))
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'leads/contract_list.html', {
        'page_obj':       page_obj,
        'q':              q,
        'status':         status,
        'status_choices': PurchaseContract.STATUS_CHOICES,
    })


@login_required
def approval_list(request):
    """承認待ち一覧（S07）— 自分宛の承認申請のみ表示"""
    profile = getattr(request.user, 'profile', None)
    is_superuser_role = (profile and profile.role == 'superuser') or request.user.is_superuser

    # 査定：自分が承認申請先になっているもの（superuserは全件）
    assessment_qs = Assessment.objects.filter(
        approved_by__isnull=True,
        status=Assessment.STATUS_CONTRACTED,
        approval_requested_to__isnull=False,
    ).select_related('customer', 'vehicle', 'assigned_to', 'approval_requested_to')
    if not is_superuser_role:
        assessment_qs = assessment_qs.filter(approval_requested_to=request.user)
    pending_assessments = assessment_qs.order_by('-approval_requested_at')

    # 契約：自分が承認申請先になっているもの（superuserは全件）
    contract_qs = PurchaseContract.objects.filter(
        approved_by__isnull=True,
        status=PurchaseContract.STATUS_PENDING,
        approval_requested_to__isnull=False,
    ).select_related('customer', 'vehicle', 'assigned_to', 'approval_requested_to')
    if not is_superuser_role:
        contract_qs = contract_qs.filter(approval_requested_to=request.user)
    pending_contracts = contract_qs.order_by('-approval_requested_at')

    # 金額訂正：superuserのみ
    pending_corrections = (
        PurchaseContract.objects.filter(
            amount_correction_flag=True,
            correction_approved_by__isnull=True,
        ).select_related('customer', 'vehicle', 'assigned_to').order_by('-contract_date')
        if is_superuser_role else PurchaseContract.objects.none()
    )

    return render(request, 'leads/approval_list.html', {
        'pending_assessments':  pending_assessments,
        'pending_contracts':    pending_contracts,
        'pending_corrections':  pending_corrections,
        'is_superuser_role':    is_superuser_role,
    })


@login_required
def contract_print(request, assessment_id):
    """買取契約書 印刷ビュー（承認済み契約のみ）"""
    assessment = get_object_or_404(
        Assessment.objects.select_related('customer', 'vehicle', 'assigned_to'),
        pk=assessment_id,
    )
    try:
        contract = PurchaseContract.objects.select_related(
            'approved_by', 'manager1', 'manager2',
        ).get(assessment=assessment)
    except PurchaseContract.DoesNotExist:
        messages.error(request, '契約が作成されていません')
        return redirect('leads:case_detail', pk=assessment_id)

    if not contract.approved_by:
        messages.error(request, '契約が承認されるまで印刷できません')
        return redirect('leads:case_detail', pk=assessment_id)

    customer     = assessment.customer
    vehicle      = assessment.vehicle
    bank_account = (
        customer.bank_accounts.filter(is_primary=True).first()
        or customer.bank_accounts.first()
    )
    recycle        = contract.recycle_amount or 0
    total_transfer = recycle + contract.purchase_price_incl_tax

    return render(request, 'leads/contract_print.html', {
        'assessment':    assessment,
        'contract':      contract,
        'customer':      customer,
        'vehicle':       vehicle,
        'bank_account':  bank_account,
        'total_transfer': total_transfer,
    })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@login_required
@require_POST
def create_contract(request, assessment_id):
    """買取契約作成 API"""
    assessment = get_object_or_404(
        Assessment.objects.select_related('customer', 'vehicle', 'assigned_to'),
        pk=assessment_id,
    )

    if assessment.status != Assessment.STATUS_CONTRACTED:
        return JsonResponse({'success': False, 'message': '成約ステータスの案件のみ契約を作成できます'}, status=400)

    try:
        _ = assessment.contract
        return JsonResponse({'success': False, 'message': 'すでに契約が作成されています'}, status=400)
    except PurchaseContract.DoesNotExist:
        pass

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    contract_date_raw = payload.get('contract_date', '')
    price_excl_raw    = payload.get('purchase_price_excl_tax', '')
    if not contract_date_raw or not price_excl_raw:
        return JsonResponse({'success': False, 'message': '契約日・買取価格（税抜）は必須です'}, status=400)

    try:
        contract_date = datetime.strptime(contract_date_raw, '%Y-%m-%d').date()
        price_excl    = Decimal(str(price_excl_raw))
        tax_rate      = Decimal(str(payload.get('tax_rate', '10'))) / Decimal('100')
        tax_amount    = (price_excl * tax_rate).quantize(Decimal('1'))
        price_incl    = price_excl + tax_amount
    except (ValueError, InvalidOperation):
        return JsonResponse({'success': False, 'message': '数値・日付の形式が不正です'}, status=400)

    recycle_amount = None
    if payload.get('recycle_amount'):
        try:
            recycle_amount = Decimal(str(payload['recycle_amount']))
        except InvalidOperation:
            pass

    User = get_user_model()

    def _get_user(uid):
        if not uid:
            return None
        try:
            return User.objects.get(pk=uid)
        except User.DoesNotExist:
            return None

    customer_name           = (payload.get('customer_name') or '').strip() or None
    customer_furigana       = (payload.get('customer_furigana') or '').strip() or None
    customer_postal_code    = (payload.get('customer_postal_code') or '').strip() or None
    customer_address        = (payload.get('customer_address') or '').strip() or None
    customer_license_number = (payload.get('customer_license_number') or '').strip() or None
    customer_occupation     = (payload.get('customer_occupation') or '').strip() or None

    try:
        with transaction.atomic():
            contract = PurchaseContract.objects.create(
                assessment=assessment,
                customer=assessment.customer,
                vehicle=assessment.vehicle,
                assigned_to=assessment.assigned_to,
                contract_date=contract_date,
                purchase_price_excl_tax=price_excl,
                tax_amount=tax_amount,
                purchase_price_incl_tax=price_incl,
                payment_scheduled_date=_parse_date(payload.get('payment_scheduled_date', '')),
                auction_scheduled_date=_parse_date(payload.get('auction_scheduled_date', '')),
                recycle_amount=recycle_amount,
                vehicle_handover_date=_parse_date(payload.get('vehicle_handover_date', '')),
                document_handover_date=_parse_date(payload.get('document_handover_date', '')),
                repair_flag=bool(payload.get('repair_flag', False)),
                repair_notes=payload.get('repair_notes', ''),
                ownership_release_flag=bool(payload.get('ownership_release_flag', False)),
                debt_remaining_flag=bool(payload.get('debt_remaining_flag', False)),
                remarks=payload.get('remarks', ''),
                repair_history_flag=_parse_tristate(payload.get('repair_history_flag')),
                meter_tampering=_parse_tristate(payload.get('meter_tampering')),
                flood_hail_damage=_parse_tristate(payload.get('flood_hail_damage')),
                malfunction=_parse_tristate(payload.get('malfunction')),
                parking_violation=_parse_tristate(payload.get('parking_violation')),
                automobile_tax_unpaid=_parse_tristate(payload.get('automobile_tax_unpaid')),
                qualified_invoice_registered=_parse_tristate(payload.get('qualified_invoice_registered')),
                invoice_registration_number=payload.get('invoice_registration_number', ''),
                manager1=_get_user(payload.get('manager1_id')),
                manager2=_get_user(payload.get('manager2_id')),
                required_inkan_count=int(payload.get('required_inkan_count') or 0),
                required_juminhyo_count=int(payload.get('required_juminhyo_count') or 0),
                required_jotohyo_count=int(payload.get('required_jotohyo_count') or 0),
                required_ininjyo_count=int(payload.get('required_ininjyo_count') or 0),
                required_jotosho_count=int(payload.get('required_jotosho_count') or 0),
                required_kanpu_count=int(payload.get('required_kanpu_count') or 0),
                updated_by=request.user,
            )
            _sync_customer_from_contract(assessment.customer, {
                'name':                        customer_name,
                'furigana':                    customer_furigana,
                'postal_code':                 customer_postal_code,
                'address':                     customer_address,
                'birth_date':                  _parse_date(payload.get('customer_birth_date', '')),
                'license_number':              customer_license_number,
                'occupation':                  customer_occupation,
                'is_taxable_business':         _parse_tristate(payload.get('qualified_invoice_registered')),
                'invoice_registration_number': payload.get('invoice_registration_number') or None,
            }, request.user)

            # 口座情報の保存
            bank_institution_type = payload.get('bank_institution_type', 'bank')
            bank_name = (payload.get('bank_name') or '').strip()
            if bank_institution_type == 'yucho' and not bank_name:
                bank_name = 'ゆうちょ銀行'
            if bank_name:
                bank_data = {
                    'bank_institution_type': bank_institution_type,
                    'bank_name':   bank_name,
                    'branch_name': (payload.get('branch_name') or '').strip(),
                    'account_type':   payload.get('account_type', '普通'),
                    'account_number': (payload.get('account_number') or '').strip(),
                    'account_holder': (payload.get('account_holder') or '').strip(),
                }
                existing = assessment.customer.bank_accounts.filter(is_primary=True).first()
                if existing:
                    for k, v in bank_data.items():
                        if v:
                            setattr(existing, k, v)
                    existing.updated_by = request.user
                    existing.save()
                else:
                    CustomerBankAccount.objects.create(
                        customer=assessment.customer,
                        is_primary=True,
                        updated_by=request.user,
                        **bank_data,
                    )
    except Exception as exc:
        logger.error(f'create_contract failed: assessment_id={assessment_id}, error={exc}')
        return JsonResponse({'success': False, 'message': '契約の作成に失敗しました'}, status=500)

    return JsonResponse({'success': True, 'message': '契約を作成しました', 'contract_id': contract.pk})


@login_required
@require_POST
def update_contract(request, contract_id):
    """買取契約更新 API"""
    contract = get_object_or_404(PurchaseContract, pk=contract_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    contract_date_raw = payload.get('contract_date', '')
    price_excl_raw    = payload.get('purchase_price_excl_tax', '')
    if not contract_date_raw or not price_excl_raw:
        return JsonResponse({'success': False, 'message': '契約日・買取価格（税抜）は必須です'}, status=400)

    try:
        contract_date = datetime.strptime(contract_date_raw, '%Y-%m-%d').date()
        price_excl    = Decimal(str(price_excl_raw))
        tax_rate      = Decimal(str(payload.get('tax_rate', '10'))) / Decimal('100')
        tax_amount    = (price_excl * tax_rate).quantize(Decimal('1'))
        price_incl    = price_excl + tax_amount
    except (ValueError, InvalidOperation) as exc:
        return JsonResponse({'success': False, 'message': f'入力値が不正です: {exc}'}, status=400)

    def _to_decimal(raw):
        if not raw:
            return None
        try:
            return Decimal(str(raw))
        except InvalidOperation:
            return None

    User = get_user_model()

    def _get_user(uid):
        if not uid:
            return None
        try:
            return User.objects.get(pk=uid)
        except User.DoesNotExist:
            return None

    qualified_invoice_reg = payload.get('qualified_invoice_registered')
    invoice_reg_number    = payload.get('invoice_registration_number', '')
    cust_name             = (payload.get('customer_name') or '').strip() or None
    cust_furigana         = (payload.get('customer_furigana') or '').strip() or None
    cust_postal_code      = (payload.get('customer_postal_code') or '').strip() or None
    cust_address          = (payload.get('customer_address') or '').strip() or None
    cust_license_number   = (payload.get('customer_license_number') or '').strip() or None
    cust_occupation       = (payload.get('customer_occupation') or '').strip() or None

    try:
        with transaction.atomic():
            contract.contract_date                = contract_date
            contract.purchase_price_excl_tax      = price_excl
            contract.tax_amount                   = tax_amount
            contract.purchase_price_incl_tax      = price_incl
            contract.recycle_amount               = _to_decimal(payload.get('recycle_amount', ''))
            contract.payment_scheduled_date       = _parse_date(payload.get('payment_scheduled_date', ''))
            contract.auction_scheduled_date       = _parse_date(payload.get('auction_scheduled_date', ''))
            contract.vehicle_handover_date        = _parse_date(payload.get('vehicle_handover_date', ''))
            contract.document_handover_date       = _parse_date(payload.get('document_handover_date', ''))
            contract.repair_flag                  = bool(payload.get('repair_flag', False))
            contract.repair_notes                 = payload.get('repair_notes', '')
            contract.ownership_release_flag       = bool(payload.get('ownership_release_flag', False))
            contract.debt_remaining_flag          = bool(payload.get('debt_remaining_flag', False))
            contract.remarks                      = payload.get('remarks', '')
            contract.manager1                     = _get_user(payload.get('manager1_id'))
            contract.manager2                     = _get_user(payload.get('manager2_id'))
            contract.required_inkan_count         = int(payload.get('required_inkan_count') or 0)
            contract.required_juminhyo_count      = int(payload.get('required_juminhyo_count') or 0)
            contract.required_jotohyo_count       = int(payload.get('required_jotohyo_count') or 0)
            contract.required_ininjyo_count       = int(payload.get('required_ininjyo_count') or 0)
            contract.required_jotosho_count       = int(payload.get('required_jotosho_count') or 0)
            contract.required_kanpu_count         = int(payload.get('required_kanpu_count') or 0)
            contract.repair_history_flag          = _parse_tristate(payload.get('repair_history_flag'))
            contract.meter_tampering              = _parse_tristate(payload.get('meter_tampering'))
            contract.flood_hail_damage            = _parse_tristate(payload.get('flood_hail_damage'))
            contract.malfunction                  = _parse_tristate(payload.get('malfunction'))
            contract.parking_violation            = _parse_tristate(payload.get('parking_violation'))
            contract.automobile_tax_unpaid        = _parse_tristate(payload.get('automobile_tax_unpaid'))
            contract.qualified_invoice_registered = _parse_tristate(qualified_invoice_reg)
            contract.invoice_registration_number  = invoice_reg_number
            contract.updated_by                   = request.user
            contract.save()

            _sync_customer_from_contract(contract.customer, {
                'name':                        cust_name,
                'furigana':                    cust_furigana,
                'postal_code':                 cust_postal_code,
                'address':                     cust_address,
                'birth_date':                  _parse_date(payload.get('customer_birth_date', '')),
                'license_number':              cust_license_number,
                'occupation':                  cust_occupation,
                'is_taxable_business':         _parse_tristate(qualified_invoice_reg),
                'invoice_registration_number': invoice_reg_number or None,
            }, request.user)

            # 口座情報の保存
            bank_institution_type = payload.get('bank_institution_type', 'bank')
            bank_name = (payload.get('bank_name') or '').strip()
            if bank_institution_type == 'yucho' and not bank_name:
                bank_name = 'ゆうちょ銀行'
            if bank_name:
                bank_data = {
                    'bank_institution_type': bank_institution_type,
                    'bank_name':   bank_name,
                    'branch_name': (payload.get('branch_name') or '').strip(),
                    'account_type':   payload.get('account_type', '普通'),
                    'account_number': (payload.get('account_number') or '').strip(),
                    'account_holder': (payload.get('account_holder') or '').strip(),
                }
                existing = contract.customer.bank_accounts.filter(is_primary=True).first()
                if existing:
                    for k, v in bank_data.items():
                        if v:
                            setattr(existing, k, v)
                    existing.updated_by = request.user
                    existing.save()
                else:
                    CustomerBankAccount.objects.create(
                        customer=contract.customer,
                        is_primary=True,
                        updated_by=request.user,
                        **bank_data,
                    )

    except (ValueError, InvalidOperation) as exc:
        return JsonResponse({'success': False, 'message': f'入力値が不正です: {exc}'}, status=400)
    except Exception as exc:
        logger.error(f'update_contract failed: contract_id={contract_id}, error={exc}')
        return JsonResponse({'success': False, 'message': '契約の更新に失敗しました'}, status=500)

    return JsonResponse({'success': True, 'message': '契約を更新しました'})


@login_required
@require_POST
def reset_contract(request, contract_id):
    """買取契約を最初から作成し直す（契約内容・契約手続の進捗を初期状態にリセット） API"""
    contract = get_object_or_404(PurchaseContract.objects.select_related('assessment'), pk=contract_id)
    assessment = contract.assessment

    total      = assessment.assessment_price or Decimal('0')
    recycle    = assessment.assessment_system_recycle_amount or Decimal('0')
    incl       = total - recycle  # リサイクル除いた税込額
    price_excl = (incl / Decimal('1.1')).quantize(Decimal('1'), rounding=ROUND_DOWN)
    tax_amount = (price_excl * Decimal('0.10')).quantize(Decimal('1'))

    with transaction.atomic():
        OwnershipRelease.objects.filter(contract=contract).delete()

        contract.contract_date           = timezone.now().date()
        contract.purchase_price_excl_tax = price_excl
        contract.tax_amount              = tax_amount
        contract.purchase_price_incl_tax = price_excl + tax_amount
        contract.recycle_amount          = recycle
        contract.payment_scheduled_date  = None
        contract.auction_scheduled_date  = None
        contract.status                  = PurchaseContract.STATUS_PENDING
        contract.cancel_reason           = ''
        contract.cancelled_at            = None
        contract.vehicle_handover_date   = None
        contract.document_handover_date  = None
        contract.amount_correction_flag  = False
        contract.corrected_price         = None
        contract.correction_approved_by  = None
        contract.correction_approved_at  = None
        contract.repair_flag             = False
        contract.repair_notes            = ''
        contract.ownership_release_flag  = False
        contract.debt_remaining_flag     = False
        contract.ownership_release_status         = PurchaseContract.OWNERSHIP_RELEASE_NOT_STARTED
        contract.ownership_release_requested_date = None
        contract.ownership_release_completed_date = None
        contract.repair_history_flag          = None
        contract.meter_tampering              = None
        contract.flood_hail_damage            = None
        contract.malfunction                  = None
        contract.parking_violation            = None
        contract.automobile_tax_unpaid        = None
        contract.qualified_invoice_registered = None
        contract.invoice_registration_number  = ''
        contract.required_inkan_count    = 0
        contract.required_juminhyo_count = 0
        contract.required_jotohyo_count  = 0
        contract.required_ininjyo_count  = 0
        contract.required_jotosho_count  = 0
        contract.required_kanpu_count    = 0
        contract.inkan_received          = False
        contract.juminhyo_received       = False
        contract.jotohyo_received        = False
        contract.ininjyo_received        = False
        contract.jotosho_received        = False
        contract.kanpu_received          = False
        contract.inkan_received_date     = None
        contract.juminhyo_received_date  = None
        contract.jotohyo_received_date   = None
        contract.ininjyo_received_date   = None
        contract.jotosho_received_date   = None
        contract.kanpu_received_date     = None
        contract.manager1                = None
        contract.manager2                = None
        contract.approved_by             = None
        contract.approved_at             = None
        contract.approval_requested_to   = None
        contract.approval_requested_at   = None
        contract.remarks                 = ''
        contract.updated_by              = request.user
        contract.save()

    return JsonResponse({'success': True, 'message': '契約をリセットしました。内容を入力し直してください。'})


@login_required
@require_POST
def upload_contract_file(request, contract_id):
    """契約手続書類のスキャン・撮影ファイルをアップロードする API"""
    contract = get_object_or_404(PurchaseContract, pk=contract_id)

    doc_type = request.POST.get('doc_type')
    if doc_type not in dict(ContractFileUpload.DOC_TYPE_CHOICES):
        return JsonResponse({'success': False, 'message': '書類種別が不正です'}, status=400)

    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'success': False, 'message': 'ファイルが選択されていません'}, status=400)

    file_obj = ContractFileUpload.objects.create(
        contract=contract,
        doc_type=doc_type,
        file=upload,
        uploaded_by=request.user,
    )

    if doc_type == 'contract_signed':
        _sync_document_done(contract, request.user)

    return JsonResponse({'success': True, 'data': _serialize_contract_file(file_obj)})


@login_required
@require_POST
def delete_contract_file(request, file_id):
    """契約手続書類ファイルを削除する API"""
    file_obj = get_object_or_404(ContractFileUpload, pk=file_id)
    doc_type = file_obj.doc_type
    contract = file_obj.contract
    file_obj.file.delete(save=False)
    file_obj.delete()

    if doc_type == 'contract_signed':
        _sync_document_done(contract, request.user)

    return JsonResponse({'success': True})


@login_required
@require_POST
def upload_aa_image(request, sp_id):
    """AA出品画像をアップロードする API"""
    sp = get_object_or_404(SalesProcess, pk=sp_id)

    image_type = request.POST.get('image_type')
    if image_type not in dict(AASaleImageUpload.IMAGE_TYPE_CHOICES):
        return JsonResponse({'success': False, 'message': '画像種別が不正です'}, status=400)

    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'success': False, 'message': 'ファイルが選択されていません'}, status=400)

    img = AASaleImageUpload.objects.create(
        sales_process=sp,
        image_type=image_type,
        file=upload,
        uploaded_by=request.user,
    )
    return JsonResponse({'success': True, 'data': _serialize_aa_image(img)})


@login_required
@require_POST
def delete_aa_image(request, image_id):
    """AA出品画像を削除する API"""
    img = get_object_or_404(AASaleImageUpload, pk=image_id)
    img.file.delete(save=False)
    img.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def update_contract_procedure(request, contract_id):
    """契約手続（所有権解除・残債）進捗更新 API"""
    contract = get_object_or_404(PurchaseContract, pk=contract_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    ownership_status = payload.get('ownership_release_status', PurchaseContract.OWNERSHIP_RELEASE_NOT_STARTED)
    if ownership_status not in {s[0] for s in PurchaseContract.OWNERSHIP_RELEASE_STATUS_CHOICES}:
        ownership_status = PurchaseContract.OWNERSHIP_RELEASE_NOT_STARTED

    contract.ownership_release_status         = ownership_status
    contract.ownership_release_requested_date = _parse_date(payload.get('ownership_release_requested_date', ''))
    contract.ownership_release_completed_date = _parse_date(payload.get('ownership_release_completed_date', ''))
    contract.updated_by                       = request.user

    with transaction.atomic():
        contract.save(update_fields=[
            'ownership_release_status', 'ownership_release_requested_date', 'ownership_release_completed_date',
            'updated_by', 'updated_at',
        ])

        if contract.debt_remaining_flag and 'or_pattern' in payload:
            or_status = payload.get('or_status', 'pending')
            valid_statuses = {s[0] for s in OwnershipRelease.STATUS_CHOICES}
            if or_status in valid_statuses:
                obj, _ = OwnershipRelease.objects.get_or_create(
                    contract=contract, defaults={'pattern': payload.get('or_pattern', 'A')},
                )
                obj.pattern                  = payload.get('or_pattern', 'A')
                obj.status                   = or_status
                obj.inquiry_status           = (payload.get('or_inquiry_status') or '').strip()
                obj.dealer_doc_sent_date     = _parse_date(payload.get('or_dealer_doc_sent_date', ''))
                obj.debt_transfer_date       = _parse_date(payload.get('or_debt_transfer_date', ''))
                obj.dealer_doc_returned_date = _parse_date(payload.get('or_dealer_doc_returned_date', ''))
                obj.save()

        _sync_document_done(contract, request.user)

    return JsonResponse({
        'success': True,
        'message': '契約手続の進捗を更新しました',
        'procedure_completed': contract.procedure_completed,
    })


@login_required
@require_POST
def request_contract_approval(request, contract_id):
    """契約承認申請 API（営業担当者が実行）"""
    contract = get_object_or_404(PurchaseContract, pk=contract_id)

    if contract.status != PurchaseContract.STATUS_PENDING:
        return JsonResponse({'success': False, 'message': '未契約の契約のみ承認申請できます'}, status=400)

    try:
        payload     = json.loads(request.body)
        approver_id = payload.get('approver_id')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if not approver_id:
        return JsonResponse({'success': False, 'message': '承認者を選択してください'}, status=400)

    User     = get_user_model()
    approver = get_object_or_404(User, pk=approver_id, is_active=True)

    contract.approval_requested_to = approver
    contract.approval_requested_at = timezone.now()
    contract.save(update_fields=['approval_requested_to', 'approval_requested_at', 'updated_at'])

    return JsonResponse({
        'success': True,
        'message': f'{ja_full_name(approver)} に承認申請しました',
        'approver_name': ja_full_name(approver),
    })


@login_required
@require_POST
def approve_contract(request, contract_id):
    """契約承認 API（承認申請先ユーザーのみ実行可）"""
    contract = get_object_or_404(PurchaseContract, pk=contract_id)

    is_designated = (
        contract.approval_requested_to_id is not None
        and contract.approval_requested_to_id == request.user.pk
    )
    profile     = getattr(request.user, 'profile', None)
    can_approve = (profile and profile.can_approve) or request.user.is_superuser
    if not (is_designated or (can_approve and contract.approval_requested_to_id is None)):
        return JsonResponse({'success': False, 'message': '承認権限がありません'}, status=403)

    try:
        payload = json.loads(request.body)
        action  = payload.get('action')
        reason  = payload.get('reason', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if action == 'approve':
        contract.approved_by = request.user
        contract.approved_at = timezone.now()
        contract.status      = PurchaseContract.STATUS_CONTRACTED
        contract.save(update_fields=['approved_by', 'approved_at', 'status', 'updated_at'])
        SalesProcess.objects.get_or_create(contract=contract)
        return JsonResponse({'success': True, 'message': '契約を承認しました'})
    elif action == 'reject':
        contract.cancel_reason             = reason
        contract.approval_requested_to     = None
        contract.approval_requested_at     = None
        contract.save(update_fields=['cancel_reason', 'approval_requested_to', 'approval_requested_at', 'updated_at'])
        return JsonResponse({'success': True, 'message': '差し戻しました'})

    return JsonResponse({'success': False, 'message': 'action が不正です'}, status=400)


@login_required
@require_POST
def approve_correction(request, contract_id):
    """金額訂正承認 API（社長のみ）"""
    profile = getattr(request.user, 'profile', None)
    is_superuser_role = (profile and profile.role == 'superuser') or request.user.is_superuser
    if not is_superuser_role:
        return JsonResponse({'success': False, 'message': '金額訂正の承認は社長のみ操作できます'}, status=403)

    contract = get_object_or_404(PurchaseContract, pk=contract_id)
    if not contract.amount_correction_flag:
        return JsonResponse({'success': False, 'message': '金額訂正フラグが立っていない契約です'}, status=400)

    try:
        payload = json.loads(request.body)
        action  = payload.get('action')
        reason  = payload.get('reason', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if action == 'approve':
        contract.correction_approved_by = request.user
        contract.correction_approved_at = timezone.now()
        contract.save(update_fields=['correction_approved_by', 'correction_approved_at', 'updated_at'])
        return JsonResponse({'success': True, 'message': '金額訂正を承認しました'})
    elif action == 'reject':
        contract.correction_approved_by = None
        contract.correction_approved_at = None
        contract.cancel_reason          = reason
        contract.save(update_fields=[
            'correction_approved_by', 'correction_approved_at', 'cancel_reason', 'updated_at'
        ])
        return JsonResponse({'success': True, 'message': '金額訂正を差し戻しました'})

    return JsonResponse({'success': False, 'message': 'action が不正です'}, status=400)


# ---------------------------------------------------------------------------
# 売掛管理
# ---------------------------------------------------------------------------

SALES_PROCESS_STEPS = [
    ('document',  '契約手続'),
    ('intake',    '入庫'),
    ('repair',    '加修'),
    ('transport', '陸送'),
    ('listing',   'AA'),
    ('sale',      '売却'),
    ('payment',   '入金'),
    ('transfer',  '振込'),
]


@login_required
def sales_process_list(request):
    """売掛管理一覧（承認者以上向け）"""
    profile = getattr(request.user, 'profile', None)
    is_approver = (profile and profile.can_approve) or request.user.is_superuser
    if not is_approver:
        messages.error(request, 'この画面はマネージャー以上のみアクセスできます')
        return redirect('leads:case_list')

    qs = SalesProcess.objects.select_related(
        'contract',
        'contract__customer',
        'contract__vehicle',
        'contract__assigned_to',
    ).order_by('contract__assigned_to__last_name', 'contract__assigned_to__first_name', 'contract__contract_date')

    sales_user_id = request.GET.get('sales_user', '').strip()
    if sales_user_id:
        qs = qs.filter(contract__assigned_to_id=sales_user_id)

    User = get_user_model()
    sales_users = User.objects.filter(
        contracts__sales_process__isnull=False,
    ).distinct().order_by('last_name', 'first_name')

    return render(request, 'leads/sales_process_list.html', {
        'processes':     qs,
        'sales_users':   sales_users,
        'sales_user_id': sales_user_id,
        'steps':         SALES_PROCESS_STEPS,
    })


@login_required
def sale_info_list(request):
    """売却情報一覧"""
    profile = getattr(request.user, 'profile', None)
    is_approver = (profile and profile.can_approve) or request.user.is_superuser
    if not is_approver:
        messages.error(request, 'この画面はマネージャー以上のみアクセスできます')
        return redirect('leads:case_list')

    has_global = request.user.is_superuser or (profile and profile.has_global_access)

    qs = SalesProcess.objects.select_related(
        'contract',
        'contract__assessment',
        'contract__assessment__assigned_to',
        'contract__assessment__assigned_to__profile',
        'contract__assessment__assigned_to__profile__store',
        'contract__vehicle',
        'sold_destination',
    ).order_by('-sold_at', '-contract__contract_date')

    # 全権限以外は自店舗のみに限定
    if not has_global and profile and profile.store:
        qs = qs.filter(contract__assessment__assigned_to__profile__store=profile.store)

    # 絞り込み（全権限のみ店舗フィルター使用可）
    f_store      = request.GET.get('store', '').strip() if has_global else ''
    f_user       = request.GET.get('user', '').strip()
    f_venue      = request.GET.get('venue', '').strip()
    f_sold_from  = request.GET.get('sold_from', '').strip()
    f_sold_to    = request.GET.get('sold_to', '').strip()

    if f_store:
        qs = qs.filter(contract__assessment__assigned_to__profile__store_id=f_store)
    if f_user:
        qs = qs.filter(contract__assessment__assigned_to_id=f_user)
    if f_venue:
        qs = qs.filter(sold_destination_id=f_venue)
    if f_sold_from:
        qs = qs.filter(sold_at__gte=f_sold_from)
    if f_sold_to:
        qs = qs.filter(sold_at__lte=f_sold_to)

    # フィルター用マスタ（担当者も表示範囲に応じて絞る）
    stores  = Store.objects.filter(is_active=True).order_by('id') if has_global else None
    User    = get_user_model()
    user_qs = User.objects.filter(
        is_active=True, assessments__contract__sales_process__isnull=False
    ).distinct().order_by('last_name', 'first_name')
    if not has_global and profile and profile.store:
        user_qs = user_qs.filter(profile__store=profile.store)
    users  = user_qs
    venues = AuctionVenue.objects.order_by('name')

    paginator = Paginator(qs, 100)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'leads/sale_info_list.html', {
        'page_obj':    page_obj,
        'stores':      stores,
        'users':       users,
        'venues':      venues,
        'f_store':     f_store,
        'f_user':      f_user,
        'f_venue':     f_venue,
        'f_sold_from': f_sold_from,
        'f_sold_to':   f_sold_to,
        'has_global':  has_global,
        'my_store':    profile.store if profile else None,
    })


@login_required
@require_POST
def toggle_sales_process_step(request, process_id):
    """売掛管理ステップ切り替え API（承認者以上のみ）"""
    profile = getattr(request.user, 'profile', None)
    is_approver = (profile and profile.can_approve) or request.user.is_superuser
    if not is_approver:
        return JsonResponse({'success': False, 'message': '権限がありません'}, status=403)

    process = get_object_or_404(SalesProcess, pk=process_id)

    try:
        payload = json.loads(request.body)
        step    = payload.get('step', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    valid_steps = [s for s, _ in SALES_PROCESS_STEPS]
    if step not in valid_steps:
        return JsonResponse({'success': False, 'message': 'ステップが不正です'}, status=400)

    field     = f'{step}_done'
    new_value = not getattr(process, field)
    setattr(process, field, new_value)
    process.updated_by = request.user
    process.save(update_fields=[field, 'updated_by', 'updated_at'])

    if step == 'transfer' and new_value:
        if not process.payment_done:
            return JsonResponse({'success': False, 'message': '「入金」が完了していません'}, status=400)
        if not process.transfer_approved_by:
            return JsonResponse({'success': False, 'message': '振込承認が必要です。先に承認申請を行ってください'}, status=400)
        process.delete()
        return JsonResponse({'success': True, 'deleted': True, 'message': '振込完了 — レコードを削除しました'})

    return JsonResponse({'success': True, 'deleted': False, 'new_value': new_value})


_MANUAL_STEPS = {'intake', 'repair', 'transport', 'listing', 'payment', 'transfer'}

# 各ステップを完了にするための前提ステップ（True=前提OK の判定関数）
def _prerequisite_ok(step, sp, contract):
    """(ok, error_msg)"""
    repair_flag = contract.repair_flag if contract else False
    if step == 'intake':
        if not sp.document_done:
            return False, '「契約手続」が完了していません'
    elif step == 'repair':
        if not sp.intake_done:
            return False, '「入庫」が完了していません'
    elif step == 'transport':
        prev_ok = sp.repair_done if repair_flag else sp.intake_done
        label   = '加修' if repair_flag else '入庫'
        if not prev_ok:
            return False, f'「{label}」が完了していません'
    elif step == 'listing':
        if not sp.transport_done:
            return False, '「陸送」が完了していません'
    elif step == 'payment':
        if not sp.sale_done:
            return False, '「売却」が完了していません'
    elif step == 'transfer':
        if not sp.payment_done:
            return False, '「入金」が完了していません'
    return True, ''


# 各ステップを取消するとき、後続が完了済なら取消不可
_STEP_SUCCESSORS = {
    'intake':    ['repair_done', 'transport_done', 'listing_done', 'sale_done'],
    'repair':    ['transport_done', 'listing_done', 'sale_done'],
    'transport': ['listing_done', 'sale_done'],
    'listing':   ['sale_done'],
    'payment':   ['transfer_done'],
    'transfer':  [],
}
_STEP_LABELS = {
    'repair': '加修', 'transport': '陸送', 'listing': 'AA',
    'sale': '売却', 'payment': '入金',
}

def _successor_ok(step, sp):
    """取消時に後続が完了していないか確認。(ok, error_msg)"""
    for field in _STEP_SUCCESSORS.get(step, []):
        if getattr(sp, field):
            label = _STEP_LABELS.get(field.replace('_done', ''), field)
            return False, f'「{label}」が完了しているため取消できません'
    return True, ''


@login_required
@require_POST
def toggle_case_sales_step(request, process_id):
    """売却フロー 手動ステップ完了/取消 API（案件担当者 or 承認権限者が操作可）"""
    process = get_object_or_404(
        SalesProcess.objects.select_related('contract__assessment__assigned_to', 'contract'),
        pk=process_id,
    )
    try:
        payload = json.loads(request.body)
        step    = payload.get('step', '')
        force   = bool(payload.get('force'))
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    if step not in _MANUAL_STEPS:
        return JsonResponse({'success': False, 'message': 'ステップが不正です'}, status=400)

    profile     = getattr(request.user, 'profile', None)
    can_approve = (profile and profile.can_approve) or request.user.is_superuser
    is_assigned = process.contract.assessment.assigned_to == request.user
    if not (is_assigned or can_approve):
        return JsonResponse({'success': False, 'message': 'この案件の担当者のみ操作できます'}, status=403)

    current   = getattr(process, f'{step}_done')
    new_value = not current

    if new_value:
        ok, msg = _prerequisite_ok(step, process, process.contract)
        if not ok:
            # 振込は前提未達の場合は常にブロック。それ以外は警告の上で強制続行を許可する。
            if step == 'transfer' or not force:
                return JsonResponse({
                    'success': False,
                    'message': msg,
                    'requires_confirm': step != 'transfer',
                }, status=400)
    else:
        ok, msg = _successor_ok(step, process)
        if not ok:
            return JsonResponse({'success': False, 'message': msg}, status=400)

    update_fields = [f'{step}_done', 'updated_by', 'updated_at']
    setattr(process, f'{step}_done', new_value)

    date_field = f'{step}_date'
    if new_value:
        date_raw = payload.get('date', '').strip()
        if date_raw:
            from datetime import date as _date
            try:
                setattr(process, date_field, _date.fromisoformat(date_raw))
                update_fields.append(date_field)
            except ValueError:
                pass
    else:
        setattr(process, date_field, None)
        update_fields.append(date_field)

    process.updated_by = request.user
    process.save(update_fields=update_fields)

    return JsonResponse({'success': True, 'new_value': new_value})


@login_required
@require_POST
def save_step_dates(request, process_id):
    """各ステップ完了日保存 API"""
    process = get_object_or_404(SalesProcess, pk=process_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    from datetime import date as _date
    step_date_fields = ['intake_date', 'repair_date', 'transport_date', 'listing_date', 'payment_date', 'transfer_date']
    update_fields = ['updated_at']
    for field in step_date_fields:
        if field in payload:
            raw = payload[field]
            if raw:
                try:
                    setattr(process, field, _date.fromisoformat(raw))
                    update_fields.append(field)
                except ValueError:
                    pass
            else:
                setattr(process, field, None)
                update_fields.append(field)

    process.save(update_fields=update_fields)
    return JsonResponse({'success': True})


@login_required
@require_POST
def update_aa_fees(request, process_id):
    """AA情報（AA会場・陸送費用）更新 API。その他費用は add_other_fee_item で管理。"""
    process = get_object_or_404(SalesProcess, pk=process_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    update_fields = ['updated_at']

    raw_venue_id = payload.get('sold_destination_id', '')
    if raw_venue_id:
        try:
            process.sold_destination = AuctionVenue.objects.get(pk=int(raw_venue_id))
        except (AuctionVenue.DoesNotExist, ValueError):
            return JsonResponse({'success': False, 'message': 'オークション会場が不正です'}, status=400)
    else:
        process.sold_destination = None
    update_fields.append('sold_destination')

    for fee_field in ('entry_fee', 'contract_fee'):
        raw = payload.get(fee_field, '')
        try:
            setattr(process, fee_field, Decimal(str(raw)) if raw != '' and raw is not None else Decimal(0))
        except (InvalidOperation, ValueError):
            return JsonResponse({'success': False, 'message': f'{fee_field} の形式が不正です'}, status=400)
        update_fields.append(fee_field)

    raw_score = payload.get('aa_score', '')
    valid_scores = {c[0] for c in SalesProcess.AA_SCORE_CHOICES}
    if raw_score in valid_scores:
        process.aa_score = raw_score
    else:
        process.aa_score = ''
    update_fields.append('aa_score')

    for fee_field in ('transport_fee_personal', 'transport_fee_auction'):
        raw = payload.get(fee_field, '')
        if raw != '' and raw is not None:
            try:
                setattr(process, fee_field, Decimal(str(raw)))
            except (InvalidOperation, ValueError):
                return JsonResponse({'success': False, 'message': f'{fee_field} の形式が不正です'}, status=400)
        else:
            setattr(process, fee_field, None)
        update_fields.append(fee_field)

    process.updated_by = request.user
    update_fields.append('updated_by')
    process.save(update_fields=update_fields)

    return JsonResponse({'success': True, 'message': 'AA情報を保存しました'})


@login_required
@require_POST
def add_other_fee_item(request, process_id):
    """その他費用明細を追加する API（multipart）"""
    process = get_object_or_404(SalesProcess, pk=process_id)

    category = request.POST.get('category', '')
    if category not in dict(OtherFeeItem.CATEGORY_CHOICES):
        return JsonResponse({'success': False, 'message': '種別が不正です'}, status=400)

    raw_amount = request.POST.get('amount', '')
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError):
        return JsonResponse({'success': False, 'message': '金額の形式が不正です'}, status=400)

    receipt = request.FILES.get('receipt_image') or None

    item = OtherFeeItem.objects.create(
        sales_process=process,
        category=category,
        amount=amount,
        receipt_image=receipt,
        created_by=request.user,
    )
    _sync_other_fee(process)

    return JsonResponse({
        'success':   True,
        'data':      _serialize_other_fee_item(item),
        'new_total': int(process.other_fee or 0),
    })


@login_required
@require_POST
def delete_other_fee_item(request, item_id):
    """その他費用明細を削除する API"""
    item = get_object_or_404(OtherFeeItem, pk=item_id)
    process = item.sales_process
    if item.receipt_image:
        item.receipt_image.delete(save=False)
    item.delete()
    _sync_other_fee(process)

    return JsonResponse({
        'success':   True,
        'new_total': int(process.other_fee or 0),
    })


@login_required
@require_POST
def update_sales_info(request, process_id):
    """売却情報（区分・売却日・売却金額）更新 API。費用は update_aa_fees で管理。"""
    process = get_object_or_404(SalesProcess, pk=process_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    valid_dispositions = {d for d, _ in SalesProcess.DISPOSITION_CHOICES}
    disposition = payload.get('vehicle_disposition', '').strip()
    if disposition and disposition not in valid_dispositions:
        return JsonResponse({'success': False, 'message': '区分が不正です'}, status=400)

    update_fields = ['updated_at']

    process.vehicle_disposition = disposition
    update_fields.append('vehicle_disposition')

    raw_sold_at = payload.get('sold_at', '')
    process.sold_at = _parse_date(raw_sold_at)
    update_fields.append('sold_at')

    raw_price = payload.get('sold_price', '')
    if raw_price != '':
        try:
            process.sold_price = Decimal(str(raw_price))
        except (InvalidOperation, ValueError):
            return JsonResponse({'success': False, 'message': '売却金額の形式が不正です'}, status=400)
    else:
        process.sold_price = None
    update_fields.append('sold_price')

    process.updated_by = request.user
    update_fields.append('updated_by')

    # sold_at が入力されたら sale_done を自動完了（AA完了が前提）
    # sold_at が空になったら sale_done をリセット（入金・振込が未完了の場合のみ）
    if process.sold_at:
        if not process.listing_done:
            return JsonResponse({'success': False, 'message': '「AA」が完了していません'}, status=400)
        if not process.sale_done:
            process.sale_done = True
            update_fields.append('sale_done')
    else:
        if process.sale_done:
            if process.payment_done:
                return JsonResponse({'success': False, 'message': '「入金」が完了しているため売却を取消できません'}, status=400)
            if process.transfer_done:
                return JsonResponse({'success': False, 'message': '「振込」が完了しているため売却を取消できません'}, status=400)
            process.sale_done = False
            update_fields.append('sale_done')

    process.save(update_fields=update_fields)

    return JsonResponse({
        'success': True,
        'message': '売却情報を保存しました',
        'sale_done': process.sale_done,
    })


# ---------------------------------------------------------------------------
# 店舗別実績
# ---------------------------------------------------------------------------

# CC以外で実績ページを表示する店舗コード
_SALES_STORE_CODES = [
    Store.TSUKUBA,
    Store.MITO,
    Store.OYAMA,
    Store.UTSUNOMIYA,
]

@login_required
def cc_performance(request):
    """後方互換: CC実績 → store_performance(CC) にリダイレクト"""
    from django.shortcuts import redirect
    return redirect('leads:store_performance', store_code=Store.CC)


@login_required
def store_performance(request, store_code):
    """店舗別実績一覧（CC: 商談取得者基準 / 営業店舗: 案件担当者基準）"""
    # 有効な店舗コードか確認
    valid_codes = [Store.CC] + _SALES_STORE_CODES
    if store_code not in valid_codes:
        from django.http import Http404
        raise Http404

    store = get_object_or_404(Store, code=store_code)
    is_cc = (store_code == Store.CC)

    # 期間フィルター（assessment_datetime 基準）
    f_from = request.GET.get('date_from', '').strip()
    f_to   = request.GET.get('date_to',   '').strip()
    f_user = request.GET.get('user',      '').strip()

    base_qs = Assessment.objects.select_related(
        'appointment_getter',
        'appointment_getter__profile',
        'appointment_getter__profile__store',
        'assigned_to',
        'assigned_to__profile',
        'assigned_to__profile__store',
        'contract',
    )

    if is_cc:
        # CC: 商談を取得した人（appointment_getter）が CC 所属のもの
        qs = base_qs.filter(appointment_getter__profile__store__code=Store.CC)
        user_filter_field = 'appointment_getter_id'
        person_field = 'appointment_getter'
    else:
        # 営業店舗: 案件担当者（assigned_to）がその店舗所属のもの
        qs = base_qs.filter(assigned_to__profile__store__code=store_code)
        user_filter_field = 'assigned_to_id'
        person_field = 'assigned_to'

    if f_from:
        qs = qs.filter(assessment_datetime__date__gte=f_from)
    if f_to:
        qs = qs.filter(assessment_datetime__date__lte=f_to)
    if f_user:
        qs = qs.filter(**{user_filter_field: f_user})

    # 個人別集計
    User = get_user_model()
    store_users = User.objects.filter(
        is_active=True,
        profile__store__code=store_code,
    ).order_by('last_name', 'first_name')

    per_person = []
    for user in store_users:
        user_qs = qs.filter(**{person_field: user})
        total       = user_qs.count()
        contracted  = user_qs.filter(status=Assessment.STATUS_CONTRACTED).count()
        managed     = user_qs.filter(status=Assessment.STATUS_MANAGED).count()
        lost        = user_qs.filter(status__in=[Assessment.STATUS_LOST, Assessment.STATUS_PRE_CANCEL]).count()
        in_progress = user_qs.filter(status=Assessment.STATUS_IN_PROGRESS).count()
        contract_rate = round(contracted / total * 100, 1) if total else 0
        purchase_total = user_qs.filter(
            status=Assessment.STATUS_CONTRACTED,
            contract__isnull=False,
        ).aggregate(s=Sum('contract__purchase_price_incl_tax'))['s'] or 0

        per_person.append({
            'user':          user,
            'total':         total,
            'in_progress':   in_progress,
            'contracted':    contracted,
            'managed':       managed,
            'lost':          lost,
            'contract_rate': contract_rate,
            'purchase_total': purchase_total,
        })

    # 全体集計
    total_all       = qs.count()
    contracted_all  = qs.filter(status=Assessment.STATUS_CONTRACTED).count()
    managed_all     = qs.filter(status=Assessment.STATUS_MANAGED).count()
    lost_all        = qs.filter(status__in=[Assessment.STATUS_LOST, Assessment.STATUS_PRE_CANCEL]).count()
    in_progress_all = qs.filter(status=Assessment.STATUS_IN_PROGRESS).count()
    rate_all        = round(contracted_all / total_all * 100, 1) if total_all else 0
    purchase_all    = qs.filter(
        status=Assessment.STATUS_CONTRACTED, contract__isnull=False,
    ).aggregate(s=Sum('contract__purchase_price_incl_tax'))['s'] or 0

    # 案件一覧（絞り込み後、最新順）
    case_qs  = qs.order_by('-assessment_datetime')
    paginator = Paginator(case_qs, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # サイドバー用: 実績ページを持つ全店舗
    perf_stores = Store.objects.filter(code__in=valid_codes, is_active=True).order_by('id')

    return render(request, 'leads/store_performance.html', {
        'store':          store,
        'is_cc':          is_cc,
        'per_person':     per_person,
        'store_users':    store_users,
        'total_all':      total_all,
        'contracted_all': contracted_all,
        'managed_all':    managed_all,
        'lost_all':       lost_all,
        'in_progress_all': in_progress_all,
        'rate_all':       rate_all,
        'purchase_all':   purchase_all,
        'page_obj':       page_obj,
        'f_from':         f_from,
        'f_to':           f_to,
        'f_user':         f_user,
        'perf_stores':    perf_stores,
    })
