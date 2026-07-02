"""
leads/views パッケージ

urls.py から直接 import できるよう、全ビュー関数を re-export する。
ビューの実装は以下のモジュールに分割されている:

  assessment.py — 査定申込フェーズ（一覧・詳細・作成・編集・API）
  case.py       — 案件・商談フェーズ（一覧・詳細・各種更新 API）
  contract.py   — 契約・承認フェーズ（一覧・印刷・作成・更新・承認 API）
  customer.py   — 顧客マスタ管理（一覧・詳細・更新・口座 API）
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
    change_appointment_getter,
    update_vehicle_info,
    import_from_assessment_system,
    save_assessment_system_id,
    update_customer_info,
    save_bank_account,
    delete_bank_account,
    request_assessment_approval,
    approve_assessment,
    cancel_contracted_assessment,
    managed_release_list,
    add_contact_history,
    add_check_item,
    delete_check_item,
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
    reset_contract,
    update_contract_procedure,
    upload_contract_file,
    delete_contract_file,
    upload_aa_image,
    delete_aa_image,
    add_other_fee_item,
    delete_other_fee_item,
    request_contract_approval,
    approve_contract,
    approve_correction,
    sales_process_list,
    sale_info_list,
    cc_performance,
    store_performance,
    toggle_sales_process_step,
    toggle_case_sales_step,
    update_aa_fees,
    update_sales_info,
    save_step_dates,
)

# --- 顧客マスタ管理 ---
from .customer import (
    customer_list,
    customer_detail,
    update_customer_direct,
    save_bank_account_direct,
    delete_bank_account_direct,
)

# --- 車両一覧 ---
from .vehicle import (
    vehicle_list,
    vehicle_list_csv,
    vehicle_list_pdf,
    inventory_table_csv,
    inventory_table_pdf,
    ledger_csv,
    ledger_pdf,
    vehicle_create,
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
    'update_assessment_info', 'update_vehicle_info', 'import_from_assessment_system',
    'save_assessment_system_id', 'update_customer_info',
    'save_bank_account', 'delete_bank_account',
    'request_assessment_approval', 'approve_assessment',
    'cancel_contracted_assessment', 'change_appointment_getter', 'managed_release_list',
    'add_contact_history', 'add_check_item', 'delete_check_item',
    'add_advance_payment', 'delete_advance_payment',
    'approve_advance_payment', 'update_required_docs',
    # contract
    'contract_list', 'approval_list', 'contract_print',
    'create_contract', 'update_contract', 'reset_contract', 'update_contract_procedure',
    'upload_contract_file', 'delete_contract_file',
    'upload_aa_image', 'delete_aa_image',
    'add_other_fee_item', 'delete_other_fee_item',
    'request_contract_approval', 'approve_contract', 'approve_correction',
    'sales_process_list', 'sale_info_list', 'cc_performance', 'store_performance',
    'toggle_sales_process_step', 'toggle_case_sales_step', 'update_aa_fees', 'update_sales_info', 'save_step_dates',
    # customer
    'customer_list', 'customer_detail',
    'update_customer_direct', 'save_bank_account_direct', 'delete_bank_account_direct',
    # vehicle
    'vehicle_list', 'vehicle_list_csv', 'vehicle_list_pdf',
    'inventory_table_csv', 'inventory_table_pdf', 'ledger_csv', 'ledger_pdf',
    'vehicle_create',
    # scraper api
    'scraper_ingest_navikuru',
]
