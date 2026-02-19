from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class LoginActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='login_activities',
        verbose_name='ユーザー',
    )
    work_date = models.DateField(db_index=True, verbose_name='勤務日')
    login_at = models.DateTimeField(db_index=True, verbose_name='出勤時刻')
    logout_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='退勤時刻')
    work_minutes = models.PositiveIntegerField(default=0, verbose_name='勤務時間（分）')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    class Meta:
        db_table = 'login_activities'
        verbose_name = 'ログイン勤怠'
        verbose_name_plural = 'ログイン勤怠'
        ordering = ['-login_at']
        indexes = [
            models.Index(fields=['user', 'work_date'], name='idx_login_act_user_date'),
            models.Index(fields=['user', 'logout_at'], name='idx_login_act_user_out'),
        ]

    def __str__(self):
        return f"{self.user} {self.login_at:%Y-%m-%d %H:%M}"

    def close_session(self, logout_time=None):
        if self.logout_at:
            return

        logout_time = logout_time or timezone.now()
        self.logout_at = logout_time
        duration = max(logout_time - self.login_at, timedelta(0))
        self.work_minutes = int(duration.total_seconds() // 60)
        self.save(update_fields=['logout_at', 'work_minutes', 'updated_at'])
