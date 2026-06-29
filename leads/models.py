from django.conf import settings
from django.db import models
from django.db.models import Q


# ---------------------------------------------------------------------------
# 顧客
# ---------------------------------------------------------------------------

class Customer(models.Model):
    """顧客"""

    name             = models.CharField(max_length=100, verbose_name='氏名')
    furigana         = models.CharField(max_length=100, blank=True, verbose_name='フリガナ')
    phone_number     = models.CharField(max_length=20, verbose_name='電話番号')
    email            = models.EmailField(max_length=255, blank=True, verbose_name='メールアドレス')
    postal_code      = models.CharField(max_length=10, blank=True, verbose_name='郵便番号')
    address          = models.CharField(max_length=255, blank=True, verbose_name='住所')
    age              = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='年齢')
    birth_date       = models.DateField(null=True, blank=True, verbose_name='生年月日')
    occupation       = models.CharField(max_length=100, blank=True, verbose_name='職業')
    gender           = models.CharField(max_length=10, blank=True, verbose_name='性別')
    family_structure = models.CharField(max_length=100, blank=True, verbose_name='家族構成')
    license_number               = models.CharField(max_length=20, blank=True, verbose_name='免許証番号')
    is_taxable_business          = models.BooleanField(null=True, blank=True, verbose_name='課税事業者')
    invoice_registration_number  = models.CharField(max_length=50, blank=True, verbose_name='インボイス登録番号')
    created_at       = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at       = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    updated_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_customers',
        verbose_name='更新者',
    )

    class Meta:
        db_table = 'customers'
        verbose_name = '顧客'
        verbose_name_plural = '顧客'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name'], name='idx_cust_name'),
            models.Index(fields=['phone_number'], name='idx_cust_phone'),
        ]

    def __str__(self):
        return f"{self.name}（{self.phone_number}）"


class CustomerBankAccount(models.Model):
    """顧客口座情報"""

    ACCOUNT_TYPE_CHOICES = [
        ('普通', '普通'),
        ('当座', '当座'),
    ]

    INSTITUTION_TYPE_CHOICES = [
        ('bank',         '銀行'),
        ('shinkin',      '信用金庫'),
        ('nokyo',        '農協'),
        ('yucho',        'ゆうちょ'),
    ]

    customer       = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bank_accounts', verbose_name='顧客')
    bank_institution_type = models.CharField(
        max_length=20,
        choices=INSTITUTION_TYPE_CHOICES,
        default='bank',
        verbose_name='金融機関種別',
    )
    bank_name      = models.CharField(max_length=100, verbose_name='銀行名')
    branch_name    = models.CharField(max_length=100, verbose_name='支店名')
    account_type   = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES, verbose_name='口座種別')
    account_number = models.CharField(max_length=20, verbose_name='口座番号')
    account_holder = models.CharField(max_length=100, verbose_name='口座名義')
    is_primary     = models.BooleanField(default=False, verbose_name='優先口座')
    created_at     = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at     = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    updated_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_bank_accounts',
        verbose_name='更新者',
    )

    class Meta:
        db_table = 'customer_bank_accounts'
        verbose_name = '顧客口座情報'
        verbose_name_plural = '顧客口座情報'

    def __str__(self):
        return f"{self.customer.name} / {self.bank_name} {self.branch_name} {self.account_number}"


# ---------------------------------------------------------------------------
# 車両
# ---------------------------------------------------------------------------

class Vehicle(models.Model):
    """車両（契約書に必要な情報のみ保持。詳細は査定システムから取り込む）"""

    # アポイント時に登録
    maker    = models.CharField(max_length=100, verbose_name='メーカー')
    car_model = models.CharField(max_length=100, verbose_name='車種')
    year     = models.CharField(max_length=10, verbose_name='年式')
    mileage  = models.CharField(max_length=20, verbose_name='走行距離')
    grade    = models.CharField(max_length=100, blank=True, verbose_name='グレード')
    color    = models.CharField(max_length=50, blank=True, verbose_name='カラー')
    displacement = models.CharField(max_length=20, blank=True, verbose_name='排気量')
    remarks  = models.TextField(blank=True, verbose_name='備考')

    # 契約書記載項目（査定システムから取り込み or 手動入力）
    chassis_number      = models.CharField(max_length=50, blank=True, verbose_name='車台番号')
    inspection_expiry   = models.DateField(null=True, blank=True, verbose_name='車検有効期限')
    registration_number = models.CharField(max_length=20, blank=True, verbose_name='登録番号（ナンバー）')
    passenger_count     = models.CharField(max_length=5, blank=True, verbose_name='乗車定員')
    body_type           = models.CharField(max_length=50, blank=True, verbose_name='ボディタイプ')
    drive_type          = models.CharField(max_length=10, blank=True, verbose_name='駆動方式')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_vehicles',
        verbose_name='更新者',
    )

    class Meta:
        db_table = 'vehicles'
        verbose_name = '車両'
        verbose_name_plural = '車両'

    def __str__(self):
        return f"{self.maker} {self.car_model}（{self.year}）"


class VehicleImage(models.Model):
    """車両画像"""

    PART_TYPE_CHOICES = [
        ('外装', '外装'),
        ('内装', '内装'),
        ('エンジン', 'エンジン'),
        ('タイヤ', 'タイヤ'),
        ('その他', 'その他'),
    ]

    vehicle    = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='images', verbose_name='車両')
    image      = models.FileField(upload_to='vehicle_images/', verbose_name='画像')
    part_type  = models.CharField(max_length=20, choices=PART_TYPE_CHOICES, blank=True, verbose_name='パーツ種別')
    taken_at   = models.DateTimeField(null=True, blank=True, verbose_name='撮影日時')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='登録日時')

    class Meta:
        db_table = 'vehicle_images'
        verbose_name = '車両画像'
        verbose_name_plural = '車両画像'

    def __str__(self):
        return f"{self.vehicle} / {self.part_type}"


# ---------------------------------------------------------------------------
# 申込番号連番管理
# ---------------------------------------------------------------------------

class NumberSequence(models.Model):
    """汎用連番管理テーブル

    sequence_type : 番号の種類（例: 'application_number', 'contract_number'）
    key           : 連番を区切る単位（例: 'NAVIKURU-20260410', '20260410'）
    last_seq      : その sequence_type × key における最終発行連番
    """

    sequence_type = models.CharField(max_length=50, verbose_name='連番種別')
    key           = models.CharField(max_length=100, verbose_name='キー')
    last_seq      = models.PositiveIntegerField(default=0, verbose_name='最終連番')

    class Meta:
        db_table = 'number_sequences'
        unique_together = [('sequence_type', 'key')]
        verbose_name = '連番管理'
        verbose_name_plural = '連番管理'

    def __str__(self):
        return f'{self.sequence_type} / {self.key} / {self.last_seq:04d}'


# ---------------------------------------------------------------------------
# 査定申込（既存 CarAssessmentRequest を拡張）
# ---------------------------------------------------------------------------

class CarAssessmentRequest(models.Model):
    """査定申込（全チャネル統合）"""

    # 対応ステータス
    STATUS_UNTOUCHED   = '未対応'
    STATUS_NO_ANSWER   = '不通'
    STATUS_SOKUPUU     = '即ぷ'
    STATUS_CALLBACK    = '再コール予定'
    STATUS_APPOINTMENT = '商談予定'
    STATUS_PROMOTED    = '商談昇格済'
    STATUS_CLOSED      = '成約'
    STATUS_LOST        = '見送り'

    FOLLOW_STATUS_CHOICES = [
        (STATUS_UNTOUCHED,   '未対応'),
        (STATUS_NO_ANSWER,   '不通'),
        (STATUS_SOKUPUU,     '即ぷ'),
        (STATUS_CALLBACK,    '再コール予定'),
        (STATUS_APPOINTMENT, '商談予定'),
        (STATUS_PROMOTED,    '商談昇格済'),
        (STATUS_CLOSED,      '成約'),
        (STATUS_LOST,        '見送り'),
    ]

    # チャネル種別
    CHANNEL_NAVIKURU    = 'NAVIKURU'
    CHANNEL_MYCAR_SCOUT = 'MYCAR_SCOUT'
    CHANNEL_CARVIEW     = 'CARVIEW'
    CHANNEL_HP          = 'HP'
    CHANNEL_WALK_IN     = 'WALK_IN'
    CHANNEL_REFERRAL    = 'REFERRAL'
    CHANNEL_EMAIL       = 'EMAIL'
    CHANNEL_MANUAL      = 'MANUAL'

    CHANNEL_CHOICES = [
        (CHANNEL_NAVIKURU,    'ナビクル'),
        (CHANNEL_MYCAR_SCOUT, 'マイカースカウト'),
        (CHANNEL_CARVIEW,     'カービュー'),
        (CHANNEL_HP,          'ホームページ'),
        (CHANNEL_WALK_IN,     '来店'),
        (CHANNEL_REFERRAL,    '紹介'),
        (CHANNEL_EMAIL,       'メール'),
        (CHANNEL_MANUAL,      '手動入力'),
    ]

    # 既存カラム（Gmail連携で使用中のため変更しない）
    application_number   = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='申込番号')
    application_datetime = models.DateTimeField(verbose_name='申込日時')
    desired_sale_timing  = models.CharField(max_length=100, blank=True, verbose_name='希望売却時期')
    maker      = models.CharField(max_length=100, blank=True, verbose_name='メーカー名')
    car_model  = models.CharField(max_length=100, blank=True, verbose_name='車種名')
    year       = models.CharField(max_length=100, blank=True, verbose_name='年式')
    mileage    = models.CharField(max_length=100, blank=True, verbose_name='走行距離')
    customer_name = models.CharField(max_length=100, verbose_name='お名前')
    phone_number  = models.CharField(max_length=20, verbose_name='電話番号')
    call_count    = models.PositiveIntegerField(default=0, verbose_name='通話数')
    postal_code   = models.CharField(max_length=10, blank=True, verbose_name='郵便番号')
    address       = models.CharField(max_length=255, blank=True, verbose_name='住所')
    email         = models.EmailField(max_length=255, blank=True, verbose_name='メールアドレス')
    sales_owner_name  = models.CharField(max_length=150, blank=True, default='', db_index=True, verbose_name='担当営業')
    sales_assigned_at = models.DateTimeField(null=True, blank=True, verbose_name='担当確定日時')
    follow_status     = models.CharField(max_length=30, choices=FOLLOW_STATUS_CHOICES, default=STATUS_UNTOUCHED, verbose_name='対応ステータス')
    sales_note        = models.TextField(blank=True, default='', verbose_name='対応コメント')
    status_updated_at = models.DateTimeField(null=True, blank=True, verbose_name='ステータス更新日時')
    status_updated_by = models.CharField(max_length=150, blank=True, default='', verbose_name='ステータス更新者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='取り込み日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    # 拡張カラム（新規追加）
    channel_type         = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_NAVIKURU, verbose_name='チャネル種別')
    customer             = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessment_requests', verbose_name='顧客')
    vehicle              = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessment_requests', verbose_name='車両')
    assigned_to          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_requests',
        verbose_name='担当者',
    )
    external_service_id  = models.CharField(max_length=100, blank=True, verbose_name='外部サービスID')
    external_status      = models.CharField(max_length=50, blank=True, verbose_name='外部ステータス')
    scraped_at           = models.DateTimeField(null=True, blank=True, verbose_name='最終スクレイピング日時')
    referral_name        = models.CharField(max_length=100, blank=True, verbose_name='紹介者名')
    reservation_datetime = models.DateTimeField(null=True, blank=True, verbose_name='査定予約日時')
    cancel_reason        = models.CharField(max_length=255, blank=True, verbose_name='キャンセル理由')

    class Meta:
        db_table = 'car_assessment_requests'
        verbose_name = '査定申込'
        verbose_name_plural = '査定申込'
        ordering = ['-application_datetime']
        indexes = [
            models.Index(fields=['-application_datetime'], name='idx_app_datetime'),
            models.Index(fields=['customer_name'], name='idx_customer_name'),
            models.Index(fields=['phone_number'], name='idx_phone_number'),
            models.Index(fields=['channel_type', 'external_service_id'], name='idx_channel_external_id'),
        ]
        # external_service_id の重複排除はアプリ層で
        # get_or_create(channel_type=..., external_service_id=...) を使用
        # MySQL は条件付き UNIQUE 制約未対応のため DB 制約は設けない

    def __str__(self):
        return f"{self.application_number} - {self.customer_name}（{self.maker} {self.car_model}）"


# ---------------------------------------------------------------------------
# 査定（商談）
# ---------------------------------------------------------------------------

class Assessment(models.Model):
    """査定（商談）— CarAssessmentRequest から昇格して生成"""

    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CONTRACTED  = 'contracted'
    STATUS_LOST        = 'lost'
    STATUS_PRE_CANCEL  = 'pre_cancel'
    STATUS_MANAGED     = 'managed'

    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, '査定中'),
        (STATUS_CONTRACTED,  '成約'),
        (STATUS_LOST,        '没'),
        (STATUS_PRE_CANCEL,  '査定前キャンセル'),
        (STATUS_MANAGED,     '管理'),
    ]

    MANAGEMENT_STATUS_CHOICES = [
        ('contract',     '契約'),
        ('lost',         '没'),
        ('re_approach',  '再アプローチ'),
    ]

    assessment_request = models.OneToOneField(
        CarAssessmentRequest,
        on_delete=models.PROTECT,
        related_name='assessment',
        verbose_name='査定申込',
    )
    customer    = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='assessments', verbose_name='顧客')
    vehicle     = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='assessments', verbose_name='車両')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assessments',
        verbose_name='担当者',
    )
    assessment_datetime = models.DateTimeField(null=True, blank=True, verbose_name='査定日時')
    assessment_price    = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='査定額')
    market_price        = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='市場相場価格')
    overall_rating      = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, verbose_name='総合評価（1〜5、0.5刻み）')
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS, verbose_name='ステータス')
    management_status   = models.CharField(max_length=20, choices=MANAGEMENT_STATUS_CHOICES, blank=True, verbose_name='管理方針')
    cancel_reason       = models.CharField(max_length=255, blank=True, verbose_name='キャンセル理由')
    cancelled_at        = models.DateTimeField(null=True, blank=True, verbose_name='キャンセル日時')
    managed_at          = models.DateTimeField(null=True, blank=True, verbose_name='管理開始日時')
    approved_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_assessments',
        verbose_name='承認者',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='承認日時')
    approval_requested_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assessment_approval_requests',
        verbose_name='承認申請先',
    )
    approval_requested_at = models.DateTimeField(null=True, blank=True, verbose_name='承認申請日時')
    remarks     = models.TextField(blank=True, verbose_name='備考')
    case_number = models.CharField(max_length=20, blank=True, unique=True, null=True, db_index=True, verbose_name='社内管理番号')

    # 査定システム連携
    assessment_system_id             = models.CharField(max_length=10, blank=True, verbose_name='査定システムID')
    assessment_system_imported_at    = models.DateTimeField(null=True, blank=True, verbose_name='査定システム取込日時')
    assessment_system_recycle_amount = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, blank=True, verbose_name='リサイクル券金額（査定システム取込）'
    )

    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    updated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_assessments',
        verbose_name='更新者',
    )

    class Meta:
        db_table = 'assessments'
        verbose_name = '査定'
        verbose_name_plural = '査定'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='idx_assessment_status'),
            models.Index(fields=['assigned_to', 'status'], name='idx_assessment_user_status'),
        ]

    def __str__(self):
        return f"{self.customer} / {self.vehicle}（{self.get_status_display()}）"


class AssessmentCheckItem(models.Model):
    """査定チェック項目"""

    CHECK_TYPE_CHOICES = [
        ('scratch',  '傷'),
        ('repair',   '修復歴'),
        ('interior', '内装'),
        ('tire',     'タイヤ'),
        ('other',    'その他'),
    ]

    assessment  = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='check_items', verbose_name='査定')
    check_type  = models.CharField(max_length=20, choices=CHECK_TYPE_CHOICES, verbose_name='チェック種別')
    description = models.TextField(blank=True, verbose_name='詳細説明')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')

    class Meta:
        db_table = 'assessment_check_items'
        verbose_name = '査定チェック項目'
        verbose_name_plural = '査定チェック項目'

    def __str__(self):
        return f"{self.assessment} / {self.get_check_type_display()}"


# ---------------------------------------------------------------------------
# 買取契約
# ---------------------------------------------------------------------------

class DocumentTypeMaster(models.Model):
    """書類種別マスタ"""

    name          = models.CharField(max_length=100, verbose_name='書類種別名')
    required_flag = models.BooleanField(default=False, verbose_name='必須')
    description   = models.TextField(blank=True, verbose_name='説明')

    class Meta:
        db_table = 'document_type_masters'
        verbose_name = '書類種別'
        verbose_name_plural = '書類種別'

    def __str__(self):
        return self.name


class PurchaseContract(models.Model):
    """買取契約"""

    STATUS_PENDING    = 'pending'
    STATUS_CONTRACTED = 'contracted'
    STATUS_CANCELLED  = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING,    '未契約'),
        (STATUS_CONTRACTED, '契約済'),
        (STATUS_CANCELLED,  '破棄'),
    ]

    assessment  = models.OneToOneField(Assessment, on_delete=models.PROTECT, related_name='contract', verbose_name='査定')
    customer    = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='contracts', verbose_name='顧客')
    vehicle     = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='contracts', verbose_name='車両')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contracts',
        verbose_name='担当者',
    )
    contract_date              = models.DateField(verbose_name='契約日')
    purchase_price_excl_tax    = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='買取確定価格（税抜）')
    tax_amount                 = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='消費税額')
    purchase_price_incl_tax    = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='買取確定価格（税込）')
    payment_scheduled_date     = models.DateField(null=True, blank=True, verbose_name='支払い予定日')
    auction_scheduled_date     = models.DateField(null=True, blank=True, verbose_name='オークション出品予定日')
    status                     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='ステータス')
    cancel_reason              = models.CharField(max_length=255, blank=True, verbose_name='キャンセル理由')
    cancelled_at               = models.DateTimeField(null=True, blank=True, verbose_name='破棄日時')
    recycle_amount             = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name='リサイクル券金額①')
    vehicle_handover_date      = models.DateField(null=True, blank=True, verbose_name='車両引渡日')
    document_handover_date     = models.DateField(null=True, blank=True, verbose_name='書類引渡日')
    amount_correction_flag     = models.BooleanField(default=False, verbose_name='金額訂正フラグ')
    corrected_price            = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='訂正後買取価格')
    correction_approved_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='correction_approved_contracts',
        verbose_name='金額訂正承認者（社長）',
    )
    correction_approved_at     = models.DateTimeField(null=True, blank=True, verbose_name='金額訂正承認日時')
    repair_flag                = models.BooleanField(default=False, verbose_name='加修フラグ')
    repair_notes               = models.TextField(blank=True, verbose_name='加修内容')
    ownership_release_flag     = models.BooleanField(default=False, verbose_name='所有権解除フラグ')
    debt_remaining_flag        = models.BooleanField(default=False, verbose_name='残債フラグ')

    # ── 契約手続 進捗（所有権解除・残債） ───────────────────────────
    OWNERSHIP_RELEASE_NOT_STARTED = 'not_started'
    OWNERSHIP_RELEASE_IN_PROGRESS = 'in_progress'
    OWNERSHIP_RELEASE_COMPLETED   = 'completed'
    OWNERSHIP_RELEASE_STATUS_CHOICES = [
        (OWNERSHIP_RELEASE_NOT_STARTED, '未対応'),
        (OWNERSHIP_RELEASE_IN_PROGRESS, '対応中'),
        (OWNERSHIP_RELEASE_COMPLETED,   '完了'),
    ]
    ownership_release_status          = models.CharField(max_length=20, choices=OWNERSHIP_RELEASE_STATUS_CHOICES, default=OWNERSHIP_RELEASE_NOT_STARTED, verbose_name='所有権解除ステータス')
    ownership_release_requested_date = models.DateField(null=True, blank=True, verbose_name='解除申請日')
    ownership_release_completed_date = models.DateField(null=True, blank=True, verbose_name='所有権解除完了日')

    # ── 車両状況・事業者登録申告（契約書記載） ──────────────────────
    repair_history_flag          = models.BooleanField(null=True, blank=True, verbose_name='修復歴')
    meter_tampering              = models.BooleanField(null=True, blank=True, verbose_name='メーター戻し・改ざん等')
    flood_hail_damage            = models.BooleanField(null=True, blank=True, verbose_name='冠水車・雹害')
    malfunction                  = models.BooleanField(null=True, blank=True, verbose_name='故障箇所')
    parking_violation            = models.BooleanField(null=True, blank=True, verbose_name='駐車違反放置反則金未納')
    automobile_tax_unpaid        = models.BooleanField(null=True, blank=True, verbose_name='自動車税未納')
    qualified_invoice_registered = models.BooleanField(null=True, blank=True, verbose_name='適格請求書発行事業者登録')
    invoice_registration_number  = models.CharField(max_length=50, blank=True, verbose_name='適格請求書登録番号')

    # ── 必要書類（通数・受取確認） ───────────────────────────────────
    required_inkan_count    = models.PositiveSmallIntegerField(default=0, verbose_name='印鑑証明（通数）')
    required_juminhyo_count = models.PositiveSmallIntegerField(default=0, verbose_name='住民票（通数）')
    required_jotohyo_count  = models.PositiveSmallIntegerField(default=0, verbose_name='除票（通数）')
    required_ininjyo_count  = models.PositiveSmallIntegerField(default=0, verbose_name='委任状（通数）')
    required_jotosho_count  = models.PositiveSmallIntegerField(default=0, verbose_name='譲渡書（通数）')
    required_kanpu_count    = models.PositiveSmallIntegerField(default=0, verbose_name='還付（通数）')
    inkan_received    = models.BooleanField(default=False, verbose_name='印鑑証明 受取済')
    juminhyo_received = models.BooleanField(default=False, verbose_name='住民票 受取済')
    jotohyo_received  = models.BooleanField(default=False, verbose_name='除票 受取済')
    ininjyo_received  = models.BooleanField(default=False, verbose_name='委任状 受取済')
    jotosho_received  = models.BooleanField(default=False, verbose_name='譲渡書 受取済')
    kanpu_received    = models.BooleanField(default=False, verbose_name='還付 受取済')
    inkan_received_date    = models.DateField(null=True, blank=True, verbose_name='印鑑証明 受領日')
    juminhyo_received_date = models.DateField(null=True, blank=True, verbose_name='住民票 受領日')
    jotohyo_received_date  = models.DateField(null=True, blank=True, verbose_name='除票 受領日')
    ininjyo_received_date  = models.DateField(null=True, blank=True, verbose_name='委任状 受領日')
    jotosho_received_date  = models.DateField(null=True, blank=True, verbose_name='譲渡書 受領日')
    kanpu_received_date    = models.DateField(null=True, blank=True, verbose_name='還付 受領日')

    # ── 担当者・責任者（契約書表示用） ─────────────────────────────
    manager1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_contracts_1',
        verbose_name='責任者1',
    )
    manager2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_contracts_2',
        verbose_name='責任者2',
    )

    approved_by                = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_contracts',
        verbose_name='承認者',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='承認日時')
    approval_requested_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contract_approval_requests',
        verbose_name='承認申請先',
    )
    approval_requested_at = models.DateTimeField(null=True, blank=True, verbose_name='承認申請日時')
    remarks     = models.TextField(blank=True, verbose_name='備考')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    updated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_contracts',
        verbose_name='更新者',
    )

    class Meta:
        db_table = 'purchase_contracts'
        verbose_name = '買取契約'
        verbose_name_plural = '買取契約'
        ordering = ['-contract_date']

    def __str__(self):
        return f"{self.customer} / {self.vehicle}（{self.get_status_display()}）"

    @property
    def all_required_docs_received(self):
        """必要通数が設定されている書類について、すべて受領済みか"""
        items = [
            (self.required_inkan_count,    self.inkan_received),
            (self.required_juminhyo_count, self.juminhyo_received),
            (self.required_jotohyo_count,  self.jotohyo_received),
            (self.required_ininjyo_count,  self.ininjyo_received),
            (self.required_jotosho_count,  self.jotosho_received),
            (self.required_kanpu_count,    self.kanpu_received),
        ]
        return all(received for count, received in items if count > 0)

    DEBT_REPAID_STATUSES = ('debt_transferred', 'docs_returned')

    @property
    def procedure_completed(self):
        """契約手続（書類受領・所有権解除・残債返済）が完了しているか"""
        if not self.all_required_docs_received:
            return False
        if self.ownership_release_flag and self.ownership_release_status != self.OWNERSHIP_RELEASE_COMPLETED:
            return False
        if self.debt_remaining_flag:
            ownership_release = getattr(self, 'ownership_release', None)
            if not ownership_release or ownership_release.status not in self.DEBT_REPAID_STATUSES:
                return False
        return True


class Document(models.Model):
    """書類・後日品"""

    STATUS_CHOICES = [
        ('not_created', '未作成'),
        ('in_progress', '作成中'),
        ('created',     '作成済'),
        ('waiting',     '受領待'),
        ('received',    '受領済'),
        ('confirmed',   '確認済'),
    ]

    LATER_SEND_CHOICES = [
        ('not_sent', '未送付'),
        ('sent',     '送付済'),
    ]

    assessment    = models.ForeignKey(Assessment, on_delete=models.CASCADE, null=True, blank=True, related_name='documents', verbose_name='査定')
    contract      = models.ForeignKey(PurchaseContract, on_delete=models.CASCADE, null=True, blank=True, related_name='documents', verbose_name='買取契約')
    document_type = models.ForeignKey(DocumentTypeMaster, on_delete=models.PROTECT, verbose_name='書類種別')
    issue_date    = models.DateField(null=True, blank=True, verbose_name='発行日')
    received_date = models.DateField(null=True, blank=True, verbose_name='受領日')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_created', verbose_name='ステータス')
    file          = models.FileField(upload_to='documents/', blank=True, verbose_name='ファイル')
    later_send_status = models.CharField(max_length=10, choices=LATER_SEND_CHOICES, default='not_sent', verbose_name='後日品送付状態')
    remarks       = models.TextField(blank=True, verbose_name='備考')
    created_at    = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at    = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    updated_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_documents',
        verbose_name='更新者',
    )

    class Meta:
        db_table = 'documents'
        verbose_name = '書類'
        verbose_name_plural = '書類'

    def __str__(self):
        return f"{self.document_type}（{self.get_status_display()}）"


class IdentityDocument(models.Model):
    """本人確認書類"""

    DOC_TYPE_CHOICES = [
        ('driving_license', '運転免許証'),
        ('passport',        'パスポート'),
        ('my_number',       'マイナンバーカード'),
        ('other',           'その他'),
    ]

    customer    = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='identity_documents', verbose_name='顧客')
    contract    = models.ForeignKey(PurchaseContract, on_delete=models.CASCADE, related_name='identity_documents', verbose_name='買取契約')
    doc_type    = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES, verbose_name='書類種別')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='確認日時')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_identity_docs',
        verbose_name='確認者',
    )
    file       = models.FileField(upload_to='identity_documents/', blank=True, verbose_name='ファイル')
    remarks    = models.TextField(blank=True, verbose_name='備考')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')

    class Meta:
        db_table = 'identity_documents'
        verbose_name = '本人確認書類'
        verbose_name_plural = '本人確認書類'

    def __str__(self):
        return f"{self.customer} / {self.get_doc_type_display()}"


class OwnershipRelease(models.Model):
    """所有権解除管理"""

    PATTERN_CHOICES = [
        ('A', 'A：ディーラー経由'),
        ('B', 'B：自己返済'),
    ]

    STATUS_CHOICES = [
        ('pending',           '未対応'),
        ('inquiry_in_progress', '残債照会中'),
        ('docs_sent',         '書類送付済'),
        ('debt_transferred',  '残債振込済'),
        ('docs_returned',     '書類返却済'),
    ]

    contract               = models.OneToOneField(PurchaseContract, on_delete=models.CASCADE, related_name='ownership_release', verbose_name='買取契約')
    pattern                = models.CharField(max_length=1, choices=PATTERN_CHOICES, verbose_name='パターン')
    inquiry_status         = models.CharField(max_length=100, blank=True, verbose_name='残債照会ステータス')
    dealer_doc_sent_date   = models.DateField(null=True, blank=True, verbose_name='ディーラーへの書類送付日')
    debt_transfer_date     = models.DateField(null=True, blank=True, verbose_name='残債振込日')
    dealer_doc_returned_date = models.DateField(null=True, blank=True, verbose_name='ディーラーからの書類返却日')
    status                 = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', verbose_name='ステータス')
    created_at             = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at             = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    class Meta:
        db_table = 'ownership_releases'
        verbose_name = '所有権解除管理'
        verbose_name_plural = '所有権解除管理'

    def __str__(self):
        return f"{self.contract} / パターン{self.pattern}（{self.get_status_display()}）"


class AdvancePayment(models.Model):
    """先払い入金記録"""

    STATUS_CHOICES = [
        ('unpaid', '未入金'),
        ('paid',   '入金済'),
    ]

    contract        = models.ForeignKey(PurchaseContract, on_delete=models.CASCADE, related_name='advance_payments', verbose_name='買取契約')
    expected_amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='入金予定額')
    payment_date    = models.DateField(null=True, blank=True, verbose_name='入金日')
    approved_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_advance_payments',
        verbose_name='承認者（社長稟議）',
    )
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unpaid', verbose_name='ステータス')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    class Meta:
        db_table = 'advance_payments'
        verbose_name = '先払い入金記録'
        verbose_name_plural = '先払い入金記録'

    def __str__(self):
        return f"{self.contract} / {self.expected_amount}円（{self.get_status_display()}）"


# ---------------------------------------------------------------------------
# 取引・連絡履歴
# ---------------------------------------------------------------------------

class ContactHistory(models.Model):
    """取引・連絡履歴（全ステップ共通）"""

    METHOD_CHOICES = [
        ('phone',  '電話'),
        ('email',  'メール'),
        ('sms',    'SMS'),
        ('visit',  '対面'),
        ('other',  'その他'),
    ]

    assessment_request = models.ForeignKey(
        CarAssessmentRequest,
        on_delete=models.CASCADE,
        related_name='contact_histories',
        verbose_name='査定申込',
    )
    customer     = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='contact_histories', verbose_name='顧客')
    recorded_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contact_histories',
        verbose_name='記録者',
    )
    contacted_at   = models.DateTimeField(verbose_name='連絡日時')
    contact_method = models.CharField(max_length=10, choices=METHOD_CHOICES, verbose_name='連絡方法')
    content        = models.TextField(verbose_name='内容')
    created_at     = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')

    class Meta:
        db_table = 'contact_histories'
        verbose_name = '取引・連絡履歴'
        verbose_name_plural = '取引・連絡履歴'
        ordering = ['-contacted_at']

    def __str__(self):
        return f"{self.assessment_request} / {self.contacted_at.strftime('%Y-%m-%d %H:%M')}"


# ---------------------------------------------------------------------------
# オークション会場マスタ
# ---------------------------------------------------------------------------

class AuctionVenue(models.Model):
    """オークション会場マスタ"""
    name          = models.CharField(max_length=100, unique=True, verbose_name='会場名')
    entry_fee     = models.DecimalField(max_digits=10, decimal_places=0, default=12100, verbose_name='出品費用（円）')
    contract_fee  = models.DecimalField(max_digits=10, decimal_places=0, default=13200, verbose_name='成約費用（円）')
    created_at    = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')

    class Meta:
        db_table     = 'auction_venues'
        verbose_name = 'オークション会場'
        verbose_name_plural = 'オークション会場'
        ordering = ['name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# 売掛管理（成約後の処理ステータス）
# ---------------------------------------------------------------------------

class SalesProcess(models.Model):
    """売掛管理 — 成約契約ごとに書類〜振込までの8ステップを追跡する。
    振込完了時はレコードごと削除される。"""

    DISPOSITION_AA        = 'aa'
    DISPOSITION_DISPLAY   = 'display'
    DISPOSITION_LOANER    = 'loaner'
    DISPOSITION_RETAIL    = 'retail'
    DISPOSITION_SCRAP     = 'scrap'

    DISPOSITION_CHOICES = [
        (DISPOSITION_AA,      'AA'),
        (DISPOSITION_DISPLAY, '展示'),
        (DISPOSITION_LOANER,  '代車'),
        (DISPOSITION_RETAIL,  '販売'),
        (DISPOSITION_SCRAP,   'ラップ'),
    ]

    contract = models.OneToOneField(
        PurchaseContract,
        on_delete=models.CASCADE,
        related_name='sales_process',
        verbose_name='買取契約',
    )

    vehicle_disposition = models.CharField(
        max_length=10,
        choices=DISPOSITION_CHOICES,
        blank=True,
        verbose_name='区分',
    )

    document_done  = models.BooleanField(default=False, verbose_name='書類')
    intake_done    = models.BooleanField(default=False, verbose_name='入庫')
    repair_done    = models.BooleanField(default=False, verbose_name='加修')
    transport_done = models.BooleanField(default=False, verbose_name='陸送')
    listing_done   = models.BooleanField(default=False, verbose_name='出品')
    sale_done      = models.BooleanField(default=False, verbose_name='売却')
    payment_done   = models.BooleanField(default=False, verbose_name='入金')
    transfer_done  = models.BooleanField(default=False, verbose_name='振込')

    intake_date    = models.DateField(null=True, blank=True, verbose_name='入庫日')
    repair_date    = models.DateField(null=True, blank=True, verbose_name='加修完了日')
    transport_date = models.DateField(null=True, blank=True, verbose_name='陸送完了日')
    listing_date   = models.DateField(null=True, blank=True, verbose_name='出品日')
    payment_date   = models.DateField(null=True, blank=True, verbose_name='入金日')
    transfer_date  = models.DateField(null=True, blank=True, verbose_name='振込日')

    sold_at          = models.DateField(null=True, blank=True, verbose_name='車両売却日')
    sold_price       = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='売却金額')
    sold_destination = models.ForeignKey(
        'AuctionVenue',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sales_processes',
        verbose_name='売却先（会場）',
    )

    transport_fee_personal = models.DecimalField(max_digits=10, decimal_places=0, default=8800, null=True, blank=True, verbose_name='個人宅陸送費用（円）')
    transport_fee_auction  = models.DecimalField(max_digits=10, decimal_places=0, default=8800, null=True, blank=True, verbose_name='オークション会場搬送費用（円）')
    other_fee              = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='その他費用（円）')

    transfer_approval_requested_at = models.DateTimeField(null=True, blank=True, verbose_name='振込承認申請日時')
    transfer_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfer_approved_processes',
        verbose_name='振込承認者',
    )
    transfer_approved_at = models.DateTimeField(null=True, blank=True, verbose_name='振込承認日時')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True,     verbose_name='更新日時')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_sales_processes',
        verbose_name='更新者',
    )

    class Meta:
        db_table = 'sales_processes'
        verbose_name = '売掛管理'
        verbose_name_plural = '売掛管理'
        ordering = ['contract__assigned_to__last_name', 'contract__contract_date']

    def __str__(self):
        return f"{self.contract.customer} / {self.contract.vehicle}"
