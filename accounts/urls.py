from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.google_login_page, name='login'),
    path('login/google/', views.google_login, name='google_login'),
    path('logout/', views.logout_view, name='logout'),
    path('clock-out/', views.clock_out_view, name='clock_out'),
]
