"""
views/utils.py — ビュー共通ヘルパー

このモジュールのシンボルを外部から直接 import しないこと。
views パッケージ内のみで使用する。
"""
import logging
from datetime import datetime

from django.db import transaction
from django.http import HttpResponseForbidden

from ..models import CarAssessmentRequest, NumberSequence

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

def _current_user_display_name(user) -> str:
    """ユーザーの表示名（姓名 > username）を返す"""
    full_name = user.get_full_name().strip()
    return full_name or user.username


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
