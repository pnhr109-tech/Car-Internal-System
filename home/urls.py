from django.urls import path

from . import views

app_name = 'home'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/calendar-events/', views.calendar_events_api, name='calendar_events_api'),
    path('api/chat-messages/', views.chat_messages_api, name='chat_messages_api'),
    path('chat/webhook/', views.google_chat_webhook, name='google_chat_webhook'),
]
