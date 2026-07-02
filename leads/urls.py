from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    # ── 査定申込 ──────────────────────────────────────────────
    path('',        views.assessment_list,   name='assessment_list'),
    path('new/',    views.assessment_create, name='assessment_create'),
    path('<int:pk>/', views.assessment_detail, name='assessment_detail'),
    path('<int:pk>/edit/', views.assessment_edit, name='assessment_edit'),

    # ── 案件（商談・契約 一気通貫） ─────────────────────────────
    path('cases/',          views.case_list,   name='case_list'),
    path('cases/<int:pk>/', views.case_detail, name='case_detail'),

    # ── 契約一覧 ─────────────────────────────────────────────
    path('contracts/', views.contract_list, name='contract_list'),

    # ── 承認待ち ─────────────────────────────────────────────
    path('approvals/', views.approval_list, name='approval_list'),

    # ── 既存 API ────────────────────────────────────────────
    path('api/assessments/',                                    views.get_assessments,                  name='get_assessments'),
    path('api/assessments/<int:request_id>/detail/',            views.get_assessment_detail,            name='get_assessment_detail'),
    path('api/latest-id/',                                      views.get_latest_assessment_id,         name='get_latest_assessment_id'),
    path('api/check-new/',                                      views.check_new_assessments,            name='check_new_assessments'),
    path('api/assessments/<int:request_id>/claim/',             views.claim_assessment_owner,           name='claim_assessment_owner'),
    path('api/assessments/<int:request_id>/call/',              views.increment_assessment_call_count,  name='increment_assessment_call_count'),
    path('api/assessments/<int:request_id>/update/',            views.update_assessment_follow_status,  name='update_assessment_follow_status'),

    # ── 新規 API ─────────────────────────────────────────────
    path('api/assessments/<int:request_id>/promote/',           views.promote_to_case,                  name='promote_to_case'),
    path('api/cases/<int:assessment_id>/update/',              views.update_assessment_info,            name='update_assessment_info'),
    path('api/cases/<int:assessment_id>/change-assignee/',     views.change_case_assignee,              name='change_case_assignee'),
    path('api/cases/<int:assessment_id>/change-appointment-getter/', views.change_appointment_getter,   name='change_appointment_getter'),
    path('api/cases/<int:assessment_id>/update-vehicle/',                views.update_vehicle_info,               name='update_vehicle_info'),
    path('api/cases/<int:assessment_id>/import-assessment-system/',  views.import_from_assessment_system,     name='import_from_assessment_system'),
    path('api/cases/<int:assessment_id>/save-assessment-system-id/', views.save_assessment_system_id,         name='save_assessment_system_id'),
    path('api/cases/<int:assessment_id>/update-customer/',     views.update_customer_info,              name='update_customer_info'),
    path('api/cases/<int:assessment_id>/save-bank-account/',   views.save_bank_account,                 name='save_bank_account'),
    path('api/bank-accounts/<int:account_id>/delete/',         views.delete_bank_account,               name='delete_bank_account'),
    path('api/cases/<int:assessment_id>/request-approval/',     views.request_assessment_approval,      name='request_assessment_approval'),
    path('api/cases/<int:assessment_id>/approve/',              views.approve_assessment,               name='approve_assessment'),
    path('api/cases/<int:assessment_id>/cancel-contracted/',    views.cancel_contracted_assessment,     name='cancel_contracted_assessment'),
    path('managed-release/',                                    views.managed_release_list,             name='managed_release_list'),
    path('api/contracts/<int:contract_id>/request-approval/',  views.request_contract_approval,        name='request_contract_approval'),
    path('api/contracts/<int:contract_id>/approve/',            views.approve_contract,                 name='approve_contract'),
    path('api/contracts/<int:contract_id>/update/',             views.update_contract,                  name='update_contract'),
    path('api/contracts/<int:contract_id>/reset/',              views.reset_contract,                   name='reset_contract'),
    path('api/contracts/<int:contract_id>/procedure/',          views.update_contract_procedure,        name='update_contract_procedure'),
    path('api/contracts/<int:contract_id>/documents/upload/',   views.upload_contract_file,             name='upload_contract_file'),
    path('api/contract-files/<int:file_id>/delete/',            views.delete_contract_file,             name='delete_contract_file'),
    path('api/sales-process/<int:sp_id>/aa-images/upload/',        views.upload_aa_image,          name='upload_aa_image'),
    path('api/aa-images/<int:image_id>/delete/',                   views.delete_aa_image,          name='delete_aa_image'),
    path('api/sales-process/<int:process_id>/other-fee-items/add/', views.add_other_fee_item,      name='add_other_fee_item'),
    path('api/other-fee-items/<int:item_id>/delete/',               views.delete_other_fee_item,   name='delete_other_fee_item'),
    path('api/contracts/<int:contract_id>/approve-correction/', views.approve_correction,               name='approve_correction'),
    path('api/history/add/',                                    views.add_contact_history,              name='add_contact_history'),
    path('cases/<int:assessment_id>/contract/print/',            views.contract_print,                   name='contract_print'),
    path('api/cases/<int:assessment_id>/create-contract/',      views.create_contract,                  name='create_contract'),
    path('api/cases/<int:assessment_id>/check-items/add/',      views.add_check_item,                   name='add_check_item'),
    path('api/check-items/<int:item_id>/delete/',               views.delete_check_item,                name='delete_check_item'),
    path('api/contracts/<int:contract_id>/advance-payments/add/', views.add_advance_payment,            name='add_advance_payment'),
    path('api/advance-payments/<int:ap_id>/delete/',            views.delete_advance_payment,           name='delete_advance_payment'),
    path('api/advance-payments/<int:ap_id>/approve/',           views.approve_advance_payment,          name='approve_advance_payment'),
    path('api/contracts/<int:contract_id>/required-docs/',      views.update_required_docs,             name='update_required_docs'),

    # ── 売掛管理 ─────────────────────────────────────────────
    path('sales-process/',                              views.sales_process_list,         name='sales_process_list'),
    path('sale-info/',                                  views.sale_info_list,             name='sale_info_list'),
    path('cc-performance/',                             views.cc_performance,             name='cc_performance'),
    path('store-performance/<str:store_code>/',         views.store_performance,          name='store_performance'),
    path('api/sales-process/<int:process_id>/toggle/',      views.toggle_sales_process_step, name='toggle_sales_process_step'),
    path('api/sales-process/<int:process_id>/step/',            views.toggle_case_sales_step,    name='toggle_case_sales_step'),
    path('api/sales-process/<int:process_id>/aa-fees/',         views.update_aa_fees,            name='update_aa_fees'),
    path('api/sales-process/<int:process_id>/update-info/',     views.update_sales_info,         name='update_sales_info'),
    path('api/sales-process/<int:process_id>/save-step-dates/', views.save_step_dates,           name='save_step_dates'),

    # ── 車両一覧 ─────────────────────────────────────────────
    path('vehicles/',                          views.vehicle_list,         name='vehicle_list'),
    path('vehicles/export/csv/',               views.vehicle_list_csv,     name='vehicle_list_csv'),
    path('vehicles/export/pdf/',               views.vehicle_list_pdf,     name='vehicle_list_pdf'),
    path('vehicles/export/inventory/csv/',     views.inventory_table_csv,  name='inventory_table_csv'),
    path('vehicles/export/inventory/pdf/',     views.inventory_table_pdf,  name='inventory_table_pdf'),
    path('vehicles/export/ledger/csv/',        views.ledger_csv,           name='ledger_csv'),
    path('vehicles/export/ledger/pdf/',        views.ledger_pdf,           name='ledger_pdf'),
    path('api/vehicles/create/',               views.vehicle_create,       name='vehicle_create'),

    # ── 顧客一覧 ─────────────────────────────────────────────
    path('customers/',                                          views.customer_list,              name='customer_list'),
    path('customers/<int:pk>/',                                 views.customer_detail,            name='customer_detail'),
    path('api/customers/<int:pk>/update/',                      views.update_customer_direct,     name='update_customer_direct'),
    path('api/customers/<int:pk>/save-bank-account/',           views.save_bank_account_direct,   name='save_bank_account_direct'),
    path('api/customers/<int:pk>/bank-accounts/<int:account_id>/delete/', views.delete_bank_account_direct, name='delete_bank_account_direct'),

    # ── スクレイパー内部 API（スクレイパープロセス専用・外部公開不可） ──
    path('internal/scraper/navikuru/', views.scraper_ingest_navikuru, name='scraper_ingest_navikuru'),
]
