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
    path('api/cases/<int:assessment_id>/update-vehicle/',      views.update_vehicle_info,               name='update_vehicle_info'),
    path('api/cases/<int:assessment_id>/update-customer/',     views.update_customer_info,              name='update_customer_info'),
    path('api/cases/<int:assessment_id>/save-bank-account/',   views.save_bank_account,                 name='save_bank_account'),
    path('api/bank-accounts/<int:account_id>/delete/',         views.delete_bank_account,               name='delete_bank_account'),
    path('api/cases/<int:assessment_id>/approve/',              views.approve_assessment,               name='approve_assessment'),
    path('api/contracts/<int:contract_id>/approve/',            views.approve_contract,                 name='approve_contract'),
    path('api/contracts/<int:contract_id>/update/',             views.update_contract,                  name='update_contract'),
    path('api/contracts/<int:contract_id>/approve-correction/', views.approve_correction,               name='approve_correction'),
    path('api/history/add/',                                    views.add_contact_history,              name='add_contact_history'),
    path('cases/<int:assessment_id>/contract/print/',            views.contract_print,                   name='contract_print'),
    path('api/cases/<int:assessment_id>/create-contract/',      views.create_contract,                  name='create_contract'),
    path('api/cases/<int:assessment_id>/check-items/add/',      views.add_check_item,                   name='add_check_item'),
    path('api/check-items/<int:item_id>/delete/',               views.delete_check_item,                name='delete_check_item'),

    # ── 顧客一覧 ─────────────────────────────────────────────
    path('customers/',                                          views.customer_list,              name='customer_list'),
    path('customers/<int:pk>/',                                 views.customer_detail,            name='customer_detail'),
    path('api/customers/<int:pk>/update/',                      views.update_customer_direct,     name='update_customer_direct'),
    path('api/customers/<int:pk>/save-bank-account/',           views.save_bank_account_direct,   name='save_bank_account_direct'),
    path('api/customers/<int:pk>/bank-accounts/<int:account_id>/delete/', views.delete_bank_account_direct, name='delete_bank_account_direct'),

    # ── Gmail Webhook ─────────────────────────────────────────
    path('webhook/gmail-push/', views.gmail_push_notification, name='gmail_push_notification'),
]
