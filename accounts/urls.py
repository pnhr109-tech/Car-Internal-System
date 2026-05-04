from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.google_login_page, name='login'),
    path('login/google/', views.google_login, name='google_login'),
    path('logout/', views.logout_view, name='logout'),
    path('clock-out/', views.clock_out_view, name='clock_out'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/new/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/<int:pk>/', views.attendance_detail, name='attendance_detail'),
    path('attendance/<int:pk>/update-day/', views.attendance_update_day, name='attendance_update_day'),
]
