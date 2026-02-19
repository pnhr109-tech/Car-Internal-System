from django.contrib import admin

from .models import LoginActivity


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'work_date', 'login_at', 'logout_at', 'work_minutes')
    list_filter = ('work_date', 'user')
    search_fields = ('user__username', 'user__email')
    ordering = ('-login_at',)
