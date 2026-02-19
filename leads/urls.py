"""
leads アプリのURLルーティング
"""
from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.assessment_list, name='assessment_list'),
    path('api/assessments/', views.get_assessments, name='get_assessments'),
    path('api/assessments/<int:request_id>/detail/', views.get_assessment_detail, name='get_assessment_detail'),
    path('api/latest-id/', views.get_latest_assessment_id, name='get_latest_assessment_id'),
    path('api/check-new/', views.check_new_assessments, name='check_new_assessments'),
    path('api/assessments/<int:request_id>/claim/', views.claim_assessment_owner, name='claim_assessment_owner'),
    path('api/assessments/<int:request_id>/update/', views.update_assessment_follow_status, name='update_assessment_follow_status'),
    path('webhook/gmail-push/', views.gmail_push_notification, name='gmail_push_notification'),
]
