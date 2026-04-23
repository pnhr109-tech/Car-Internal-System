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
    CarAssessmentRequest,
    ContactHistory,
    Customer,
    CustomerBankAccount,
    PurchaseContract,
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
    """承認待ち一覧（S07）"""
    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.can_approve) and not request.user.is_superuser:
        messages.error(request, '承認権限がありません')
        return redirect('leads:assessment_list')

    pending_appointments = CarAssessmentRequest.objects.filter(
        follow_status=CarAssessmentRequest.STATUS_APPOINTMENT,
    ).select_related('customer', 'vehicle').order_by('-status_updated_at')

    pending_assessments = Assessment.objects.filter(
        approved_by__isnull=True,
        status=Assessment.STATUS_CONTRACTED,
    ).select_related('customer', 'vehicle', 'assigned_to').order_by('-created_at')

    pending_contracts = PurchaseContract.objects.filter(
        approved_by__isnull=True,
        status=PurchaseContract.STATUS_PENDING,
    ).select_related('customer', 'vehicle', 'assigned_to').order_by('-contract_date')

    is_superuser_role = (profile and profile.role == 'superuser') or request.user.is_superuser
    pending_corrections = (
        PurchaseContract.objects.filter(
            amount_correction_flag=True,
            correction_approved_by__isnull=True,
        ).select_related('customer', 'vehicle', 'assigned_to').order_by('-contract_date')
        if is_superuser_role else PurchaseContract.objects.none()
    )

    return render(request, 'leads/approval_list.html', {
        'pending_appointments': pending_appointments,
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
def approve_contract(request, contract_id):
    """契約承認 API"""
    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.can_approve) and not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': '承認権限がありません'}, status=403)

    contract = get_object_or_404(PurchaseContract, pk=contract_id)
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
        return JsonResponse({'success': True, 'message': '契約を承認しました'})
    elif action == 'reject':
        contract.cancel_reason = reason
        contract.save(update_fields=['cancel_reason', 'updated_at'])
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
