"""
leads/views パッケージ

urls.py から直接 import できるよう、全ビュー関数を re-export する。
ビューの実装は以下のモジュールに分割されている:

  assessment.py — 査定申込フェーズ（一覧・詳細・作成・編集・API）
  case.py       — 案件・商談フェーズ（一覧・詳細・各種更新 API）
  contract.py   — 契約・承認フェーズ（一覧・印刷・作成・更新・承認 API）
  customer.py   — 顧客マスタ管理（一覧・詳細・更新・口座 API）
  webhook.py    — 外部 Webhook（Gmail Push通知）
  utils.py      — ビュー内共通ヘルパー（外部から直接 import しないこと）
"""

# --- 査定申込フェーズ ---
from .assessment import (
    assessment_list,
    assessment_detail,
    assessment_create,
    assessment_edit,
    get_assessments,
    check_new_assessments,
    get_latest_assessment_id,
    get_assessment_detail,
    claim_assessment_owner,
    increment_assessment_call_count,
    update_assessment_follow_status,
    promote_to_case,
)

# --- 案件・商談フェーズ ---
from .case import (
    case_list,
    case_detail,
    update_assessment_info,
    change_case_assignee,
    update_vehicle_info,
    update_customer_info,
    save_bank_account,
    delete_bank_account,
    approve_assessment,
    add_contact_history,
    add_check_item,
    delete_check_item,
    update_ownership_release,
    add_advance_payment,
    delete_advance_payment,
    approve_advance_payment,
    update_required_docs,
)

# --- 契約・承認フェーズ ---
from .contract import (
    contract_list,
    approval_list,
    contract_print,
    create_contract,
    update_contract,
    approve_contract,
    approve_correction,
)

# --- 顧客マスタ管理 ---
from .customer import (
    customer_list,
    customer_detail,
    update_customer_direct,
    save_bank_account_direct,
    delete_bank_account_direct,
)

# --- Webhook ---
from .webhook import (
    gmail_push_notification,
)

# --- スクレイパー内部 API ---
from .scraper_api import (
    scraper_ingest_navikuru,
)

__all__ = [
    # assessment
    'assessment_list', 'assessment_detail', 'assessment_create', 'assessment_edit',
    'get_assessments', 'check_new_assessments', 'get_latest_assessment_id',
    'get_assessment_detail', 'claim_assessment_owner', 'increment_assessment_call_count',
    'update_assessment_follow_status', 'promote_to_case',
    # case
    'case_list', 'case_detail',
    'update_assessment_info', 'update_vehicle_info', 'update_customer_info',
    'save_bank_account', 'delete_bank_account', 'approve_assessment',
    'add_contact_history', 'add_check_item', 'delete_check_item',
    'update_ownership_release', 'add_advance_payment', 'delete_advance_payment',
    'approve_advance_payment', 'update_required_docs',
    # contract
    'contract_list', 'approval_list', 'contract_print',
    'create_contract', 'update_contract', 'approve_contract', 'approve_correction',
    # customer
    'customer_list', 'customer_detail',
    'update_customer_direct', 'save_bank_account_direct', 'delete_bank_account_direct',
    # webhook
    'gmail_push_notification',
    # scraper api
    'scraper_ingest_navikuru',
]
