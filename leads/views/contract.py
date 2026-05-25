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
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import (
    Assessment,
    AuctionVenue,
    CarAssessmentRequest,
    ContactHistory,
    Customer,
    CustomerBankAccount,
    PurchaseContract,
    SalesProcess,
    Vehicle,
)
from .utils import _parse_tristate, _parse_date, _sync_customer_from_contract

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
        'message': f'{approver.get_full_name() or approver.username} に承認申請しました',
        'approver_name': approver.get_full_name() or approver.username,
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
    ('document',  '書類'),
    ('intake',    '入庫'),
    ('repair',    '加修'),
    ('transport', '陸送'),
    ('listing',   '出品'),
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


_MANUAL_STEPS = {'intake', 'repair', 'transport', 'listing', 'payment'}

# 各ステップを完了にするための前提ステップ（True=前提OK の判定関数）
def _prerequisite_ok(step, sp, contract):
    """(ok, error_msg)"""
    repair_flag = contract.repair_flag if contract else False
    if step == 'intake':
        if not sp.document_done:
            return False, '「書類」が完了していません'
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
    return True, ''


# 各ステップを取消するとき、後続が完了済なら取消不可
_STEP_SUCCESSORS = {
    'intake':    ['repair_done', 'transport_done', 'listing_done', 'sale_done'],
    'repair':    ['transport_done', 'listing_done', 'sale_done'],
    'transport': ['listing_done', 'sale_done'],
    'listing':   ['sale_done'],
    'payment':   [],
}
_STEP_LABELS = {
    'repair': '加修', 'transport': '陸送', 'listing': '出品',
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
            return JsonResponse({'success': False, 'message': msg}, status=400)
    else:
        ok, msg = _successor_ok(step, process)
        if not ok:
            return JsonResponse({'success': False, 'message': msg}, status=400)

    field = f'{step}_done'
    setattr(process, field, new_value)
    process.updated_by = request.user
    process.save(update_fields=[field, 'updated_by', 'updated_at'])

    return JsonResponse({'success': True, 'new_value': new_value})


@login_required
@require_POST
def update_sales_info(request, process_id):
    """売却情報（区分・売却日・売却金額・売却先・各種費用）更新 API"""
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

    raw_venue_id = payload.get('sold_destination_id', '')
    if raw_venue_id:
        try:
            process.sold_destination = AuctionVenue.objects.get(pk=int(raw_venue_id))
        except (AuctionVenue.DoesNotExist, ValueError):
            return JsonResponse({'success': False, 'message': 'オークション会場が不正です'}, status=400)
    else:
        process.sold_destination = None
    update_fields.append('sold_destination')

    for fee_field in ('transport_fee_personal', 'transport_fee_auction', 'other_fee'):
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

    # sold_at が入力されたら sale_done を自動完了（出品完了が前提）
    if process.sold_at:
        if not process.listing_done:
            return JsonResponse({'success': False, 'message': '「出品」が完了していません'}, status=400)
        if not process.sale_done:
            process.sale_done = True
            update_fields.append('sale_done')

    process.save(update_fields=update_fields)

    return JsonResponse({
        'success': True,
        'message': '売却情報を保存しました',
        'sale_done': process.sale_done,
    })
