"""
views/customer.py — 顧客マスタ管理ビュー

- customer_list          : 顧客一覧（S08）
- customer_detail        : 顧客詳細・編集
- update_customer_direct : 顧客情報更新 API
- save_bank_account_direct   : 口座情報追加・更新 API
- delete_bank_account_direct : 口座情報削除 API
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ..models import Assessment, Customer, CustomerBankAccount
from .utils import _parse_date, _require_manager

logger = logging.getLogger(__name__)


@login_required
def customer_list(request):
    """顧客一覧（マネージャー・全権限のみ）"""
    denied = _require_manager(request)
    if denied:
        return denied

    q = request.GET.get('q', '').strip()
    qs = Customer.objects.prefetch_related('bank_accounts').order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(phone_number__icontains=q) |
            Q(email__icontains=q)
        )

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'leads/customer_list.html', {
        'page_obj': page,
        'q': q,
        'total_count': qs.count(),
    })


@login_required
def customer_detail(request, pk):
    """顧客詳細・編集（マネージャー・全権限のみ）"""
    denied = _require_manager(request)
    if denied:
        return denied

    customer = get_object_or_404(
        Customer.objects.prefetch_related('bank_accounts', 'contracts__assessment'),
        pk=pk,
    )
    assessments = Assessment.objects.filter(customer=customer).select_related(
        'vehicle', 'assigned_to', 'assessment_request'
    ).order_by('-created_at')

    return render(request, 'leads/customer_detail.html', {
        'customer': customer,
        'bank_accounts': customer.bank_accounts.all(),
        'assessments': assessments,
    })


@login_required
@require_POST
def update_customer_direct(request, pk):
    """顧客直接編集 API（顧客詳細ページから）"""
    denied = _require_manager(request)
    if denied:
        return denied

    customer = get_object_or_404(Customer, pk=pk)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    str_fields = [
        'name', 'furigana', 'phone_number', 'email', 'postal_code', 'address',
        'occupation', 'gender', 'family_structure', 'license_number',
        'invoice_registration_number',
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
        customer.birth_date = _parse_date(payload['birth_date'])
        update_fields.append('birth_date')

    if 'is_taxable_business' in payload:
        val = payload['is_taxable_business']
        customer.is_taxable_business = None if val is None else bool(val)
        update_fields.append('is_taxable_business')

    customer.updated_by = request.user
    update_fields.append('updated_by')
    customer.save(update_fields=list(set(update_fields)))
    return JsonResponse({'success': True, 'message': '顧客情報を更新しました'})


@login_required
@require_POST
def save_bank_account_direct(request, pk):
    """口座情報追加・更新 API（顧客詳細ページから）"""
    denied = _require_manager(request)
    if denied:
        return denied

    customer = get_object_or_404(Customer, pk=pk)

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
def delete_bank_account_direct(request, pk, account_id):
    """口座情報削除 API（顧客詳細ページから）"""
    denied = _require_manager(request)
    if denied:
        return denied

    acc = get_object_or_404(CustomerBankAccount, pk=account_id, customer_id=pk)
    acc.delete()
    return JsonResponse({'success': True, 'message': '口座情報を削除しました'})
