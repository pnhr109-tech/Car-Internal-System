"""
views/utils.py — ビュー共通ヘルパー

このモジュールのシンボルを外部から直接 import しないこと。
views パッケージ内のみで使用する。
"""
import logging
import os
from datetime import datetime

from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.utils import timezone

from ..models import CarAssessmentRequest, NumberSequence, OtherFeeItem, SalesProcess

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 申込番号生成
# ---------------------------------------------------------------------------

_CHANNEL_PREFIX = {
    CarAssessmentRequest.CHANNEL_NAVIKURU:    'N',
    CarAssessmentRequest.CHANNEL_MYCAR_SCOUT: 'M',
    CarAssessmentRequest.CHANNEL_CARVIEW:     'C',
    CarAssessmentRequest.CHANNEL_HP:          'H',
    CarAssessmentRequest.CHANNEL_WALK_IN:     'W',
    CarAssessmentRequest.CHANNEL_REFERRAL:    'R',
    CarAssessmentRequest.CHANNEL_EMAIL:       'E',
}


def _next_seq(sequence_type: str, key: str) -> int:
    """汎用連番発行（行ロックで重複防止）"""
    with transaction.atomic():
        NumberSequence.objects.get_or_create(
            sequence_type=sequence_type,
            key=key,
            defaults={'last_seq': 0},
        )
        obj = NumberSequence.objects.select_for_update().get(
            sequence_type=sequence_type,
            key=key,
        )
        obj.last_seq += 1
        obj.save(update_fields=['last_seq'])
    return obj.last_seq


def _generate_application_number(channel_type: str, today) -> str:
    """査定申込番号を生成"""
    ch_prefix = _CHANNEL_PREFIX.get(channel_type, 'X')
    key = f'{channel_type}-{today.strftime("%Y%m%d")}'
    seq = _next_seq('application_number', key)
    return f'{ch_prefix}-{today.strftime("%Y%m%d")}-{seq:04d}'


def generate_case_number() -> str:
    """社内管理番号を生成（形式: YYMMDD-NNNN 例: 260617-0001）"""
    from datetime import date
    today = date.today()
    key = today.strftime('%y%m%d')
    seq = _next_seq('case_number', key)
    return f'{key}-{seq:04d}'


# ---------------------------------------------------------------------------
# ユーザー
# ---------------------------------------------------------------------------

def ja_full_name(user) -> str:
    """姓名順でフルネームを返す（日本語表示用）。未設定時は username にフォールバック。"""
    if user is None:
        return ''
    last  = (getattr(user, 'last_name',  '') or '').strip()
    first = (getattr(user, 'first_name', '') or '').strip()
    full  = f'{last} {first}'.strip()
    return full or (getattr(user, 'username', '') or '')


def _current_user_display_name(user) -> str:
    """ユーザーの表示名（姓名順 > username）を返す"""
    return ja_full_name(user)


# ---------------------------------------------------------------------------
# 権限チェック
# ---------------------------------------------------------------------------

def _require_manager(request):
    """マネージャー以上の権限チェック。権限なしなら HttpResponseForbidden を返す"""
    profile = getattr(request.user, 'profile', None)
    if request.user.is_superuser:
        return None
    if profile and profile.role in ('manager', 'superuser'):
        return None
    return HttpResponseForbidden('この操作にはマネージャー以上の権限が必要です')


# ---------------------------------------------------------------------------
# 型変換ヘルパー
# ---------------------------------------------------------------------------

def _parse_tristate(val):
    """JSON の true/false/null を BooleanField 用に変換"""
    if val is None:
        return None
    return bool(val)


def _parse_date(raw: str):
    """'YYYY-MM-DD' 文字列を date に変換。空文字・不正値は None"""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 契約手続ステップ 自動同期
# ---------------------------------------------------------------------------

def _sync_document_done(contract, updated_by) -> bool:
    """SalesProcess.document_done を contract.procedure_completed に同期する。

    案件フローの「契約手続」ステップ表示が、契約手続タブの完了バッジ
    （書類受領・所有権解除・残債返済を含む procedure_completed）とズレないようにする。
    戻り値は document_done が変化したかどうか。
    """
    try:
        sp = SalesProcess.objects.get(contract=contract)
    except SalesProcess.DoesNotExist:
        return False

    completed = contract.procedure_completed
    if sp.document_done == completed:
        return False

    sp.document_done = completed
    sp.updated_by = updated_by
    sp.save(update_fields=['document_done', 'updated_by', 'updated_at'])
    return True


# ---------------------------------------------------------------------------
# 顧客マスタ自動反映
# ---------------------------------------------------------------------------

def _sync_customer_from_contract(customer, payload_map: dict, updated_by) -> None:
    """契約書入力内容を顧客マスタに自動反映する。

    payload_map: {customer_field: value} の辞書。
    値が None の場合は「未送信」として扱い、既存値を変更しない。
    """
    update_fields = ['updated_by']

    # name・address・postal_code は値があれば常に更新する
    for f in ('name', 'address', 'postal_code'):
        if f in payload_map and payload_map[f]:
            setattr(customer, f, payload_map[f])
            update_fields.append(f)

    for f in ('furigana', 'invoice_registration_number', 'occupation'):
        if f in payload_map and payload_map[f] is not None:
            setattr(customer, f, payload_map[f])
            update_fields.append(f)

    if 'is_taxable_business' in payload_map and payload_map['is_taxable_business'] is not None:
        customer.is_taxable_business = bool(payload_map['is_taxable_business'])
        update_fields.append('is_taxable_business')

    for f in ('birth_date', 'license_number'):
        if f in payload_map and payload_map[f] is not None:
            setattr(customer, f, payload_map[f])
            update_fields.append(f)

    customer.updated_by = updated_by
    customer.save(update_fields=list(set(update_fields)))


# ---------------------------------------------------------------------------
# 契約書類ファイル
# ---------------------------------------------------------------------------

def _serialize_contract_file(file_obj) -> dict:
    """ContractFileUpload を JS 側で扱いやすい dict に変換する"""
    uploaded_by = file_obj.uploaded_by
    return {
        'id':          file_obj.id,
        'doc_type':    file_obj.doc_type,
        'url':         file_obj.file.url,
        'filename':    os.path.basename(file_obj.file.name),
        'uploaded_at': timezone.localtime(file_obj.uploaded_at).strftime('%Y/%m/%d %H:%M'),
        'uploaded_by': ja_full_name(uploaded_by) if uploaded_by else '-',
    }


def _serialize_aa_image(img) -> dict:
    """AASaleImageUpload を JS 側で扱いやすい dict に変換する"""
    uploaded_by = img.uploaded_by
    return {
        'id':          img.id,
        'image_type':  img.image_type,
        'url':         img.file.url,
        'filename':    os.path.basename(img.file.name),
        'uploaded_at': timezone.localtime(img.uploaded_at).strftime('%Y/%m/%d %H:%M'),
        'uploaded_by': ja_full_name(uploaded_by) if uploaded_by else '-',
    }


# ---------------------------------------------------------------------------
# その他費用明細
# ---------------------------------------------------------------------------

def _serialize_other_fee_item(item) -> dict:
    """OtherFeeItem を JS 側で扱いやすい dict に変換する"""
    created_by = item.created_by
    return {
        'id':              item.id,
        'category':        item.category,
        'category_label':  item.get_category_display(),
        'amount':          int(item.amount),
        'receipt_url':     item.receipt_image.url if item.receipt_image else None,
        'receipt_filename': os.path.basename(item.receipt_image.name) if item.receipt_image else None,
        'created_at':      timezone.localtime(item.created_at).strftime('%Y/%m/%d %H:%M'),
        'created_by':      ja_full_name(created_by) if created_by else '-',
    }


def _sync_other_fee(sales_process) -> None:
    """OtherFeeItem 合計を SalesProcess.other_fee に同期する"""
    from decimal import Decimal
    total = sales_process.other_fee_items.aggregate(total=Sum('amount'))['total']
    sales_process.other_fee = total if total is not None else Decimal(0)
    SalesProcess.objects.filter(pk=sales_process.pk).update(other_fee=sales_process.other_fee)
