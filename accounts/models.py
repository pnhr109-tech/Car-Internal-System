from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Store(models.Model):
    """店舗マスタ"""

    TSUKUBA    = 'TSUKUBA'
    MITO       = 'MITO'
    OYAMA      = 'OYAMA'
    UTSUNOMIYA = 'UTSUNOMIYA'
    CC         = 'CC'
    SUPPORT    = 'SUPPORT'
    HQ         = 'HQ'

    CODE_CHOICES = [
        (TSUKUBA,    'つくば'),
        (MITO,       '水戸'),
        (OYAMA,      '小山'),
        (UTSUNOMIYA, '宇都宮'),
        (CC,         'コンタクトセンター'),
        (SUPPORT,    'サポート'),
        (HQ,         '本社業務'),
    ]

    code      = models.CharField(max_length=20, unique=True, choices=CODE_CHOICES, verbose_name='店舗コード')
    name      = models.CharField(max_length=50, verbose_name='店舗名')
    is_active = models.BooleanField(default=True, verbose_name='有効')

    class Meta:
        db_table = 'stores'
        verbose_name = '店舗'
        verbose_name_plural = '店舗'
        ordering = ['id']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """ユーザープロファイル（社員情報・権限）"""

    ROLE_GENERAL    = 'general'
    ROLE_SUB_LEADER = 'sub_leader'
    ROLE_MANAGER    = 'manager'
    ROLE_SUPERUSER  = 'superuser'

    ROLE_CHOICES = [
        (ROLE_GENERAL,    '一般社員'),
        (ROLE_SUB_LEADER, '次席'),
        (ROLE_MANAGER,    'マネージャー'),
        (ROLE_SUPERUSER,  '全権限'),
    ]

    user                = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='ユーザー',
    )
    store               = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='members',
        verbose_name='所属店舗',
        help_text='全権限ロールの場合はNULL',
    )
    role                = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_GENERAL, verbose_name='ロール')
    employee_number     = models.CharField(max_length=20, blank=True, verbose_name='社員番号')
    is_active_employee  = models.BooleanField(default=True, verbose_name='在籍中')
    created_at          = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at          = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'ユーザープロファイル'
        verbose_name_plural = 'ユーザープロファイル'

    def __str__(self):
        store_name = self.store.name if self.store else '（店舗なし）'
        return f"{self.user.get_full_name() or self.user.username} [{store_name} / {self.get_role_display()}]"

    @property
    def has_global_access(self):
        """全店舗データを参照できるか（superuser または 本社業務所属）"""
        return self.role == self.ROLE_SUPERUSER or (self.store and self.store.code == Store.HQ)

    @property
    def can_approve(self):
        """承認操作ができるか"""
        return self.role in (self.ROLE_SUB_LEADER, self.ROLE_MANAGER, self.ROLE_SUPERUSER)

    @property
    def can_edit_numbers(self):
        """数字系データを変更できるか（一般社員は不可）"""
        return self.role in (self.ROLE_SUB_LEADER, self.ROLE_MANAGER, self.ROLE_SUPERUSER)

    def can_access_store(self, store):
        """指定店舗のデータにアクセスできるか"""
        if self.has_global_access:
            return True
        return self.store_id == store.id


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
