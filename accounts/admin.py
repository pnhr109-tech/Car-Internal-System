from django.contrib import admin

from .models import LoginActivity, Store, UserProfile


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    ordering = ('id',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'store', 'role', 'employee_number', 'is_active_employee')
    list_filter = ('store', 'role', 'is_active_employee')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'employee_number')
    raw_id_fields = ('user',)


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'work_date', 'login_at', 'logout_at', 'work_minutes')
    list_filter = ('work_date', 'user')
    search_fields = ('user__username', 'user__email')
    ordering = ('-login_at',)
