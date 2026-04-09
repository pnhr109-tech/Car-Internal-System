from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    # ── 査定申込 ──────────────────────────────────────────────
    path('',        views.assessment_list,   name='assessment_list'),
    path('new/',    views.assessment_create, name='assessment_create'),
    path('<int:pk>/', views.assessment_detail, name='assessment_detail'),

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
    path('api/cases/<int:assessment_id>/approve/',              views.approve_assessment,               name='approve_assessment'),
    path('api/contracts/<int:contract_id>/approve/',            views.approve_contract,                 name='approve_contract'),
    path('api/history/add/',                                    views.add_contact_history,              name='add_contact_history'),

    # ── Gmail Webhook ─────────────────────────────────────────
    path('webhook/gmail-push/', views.gmail_push_notification, name='gmail_push_notification'),
]
