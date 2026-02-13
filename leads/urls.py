"""
leads アプリのURLルーティング
"""
from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.assessment_list, name='assessment_list'),
    path('api/assessments/', views.get_assessments, name='get_assessments'),
    path('api/check-new/', views.check_new_assessments, name='check_new_assessments'),
    path('webhook/gmail-push/', views.gmail_push_notification, name='gmail_push_notification'),
]
