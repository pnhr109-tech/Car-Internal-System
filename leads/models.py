from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------

class GmailMessage(models.Model):
    """Gmail メッセージを保存するモデル（重複防止対応）"""

    message_id   = models.CharField(max_length=255, unique=True, db_index=True, verbose_name='メッセージID')
    thread_id    = models.CharField(max_length=255, db_index=True, verbose_name='スレッドID')
    from_address = models.EmailField(max_length=255, verbose_name='送信元')
    to_address   = models.EmailField(max_length=255, verbose_name='宛先')
    subject      = models.CharField(max_length=500, verbose_name='件名')
    received_at  = models.DateTimeField(db_index=True, verbose_name='受信日時')
    created_at   = models.DateTimeField(auto_now_add=True, verbose_name='取り込み日時')
    snippet      = models.TextField(blank=True, null=True, verbose_name='スニペット')
    body_text    = models.TextField(blank=True, null=True, verbose_name='本文（テキスト）')
    body_html    = models.TextField(blank=True, null=True, verbose_name='本文（HTML）')
    raw_json     = models.JSONField(blank=True, null=True, verbose_name='Gmail API レスポンス')

    class Meta:
        db_table = 'gmail_messages'
        verbose_name = 'Gmailメッセージ'
        verbose_name_plural = 'Gmailメッセージ'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['-received_at'], name='idx_received_at'),
        ]

    def __str__(self):
        return f"{self.received_at.strftime('%Y-%m-%d %H:%M')} - {self.subject}"


# ---------------------------------------------------------------------------
# 顧客
# ---------------------------------------------------------------------------

class Customer(models.Model):
    """顧客"""

    name             = models.CharField(max_length=100, verbose_name='氏名')
    phone_number     = models.CharField(max_length=20, verbose_name='電話番号')
    email            = models.EmailField(max_length=255, blank=True, verbose_name='メールアドレス')
    postal_code      = models.CharField(max_length=10, blank=True, verbose_name='郵便番号')
    address          = models.CharField(max_length=255, blank=True, verbose_name='住所')
    age              = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='年齢')
    occupation       = models.CharField(max_length=100, blank=True, verbose_name='職業')
    gender           = models.CharField(max_length=10, blank=True, verbose_name='性別')
    family_structure = models.CharField(max_length=100, blank=True, verbose_name='家族構成')
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

    customer       = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bank_accounts', verbose_name='顧客')
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
    """車両"""

    TRANSMISSION_CHOICES = [
        ('AT', 'AT'),
        ('MT', 'MT'),
        ('CVT', 'CVT'),
        ('その他', 'その他'),
    ]

    # ①アポイント時に登録
    maker    = models.CharField(max_length=100, verbose_name='メーカー')
    car_model = models.CharField(max_length=100, verbose_name='車種')
    year     = models.CharField(max_length=10, verbose_name='年式')
    mileage  = models.CharField(max_length=20, verbose_name='走行距離')
    grade    = models.CharField(max_length=100, blank=True, verbose_name='グレード')
    color    = models.CharField(max_length=50, blank=True, verbose_name='カラー')
    displacement = models.CharField(max_length=20, blank=True, verbose_name='排気量')
    remarks  = models.TextField(blank=True, verbose_name='備考')

    # ②商談時に追加
    chassis_number        = models.CharField(max_length=50, blank=True, verbose_name='車台番号')
    first_registration_date = models.DateField(null=True, blank=True, verbose_name='初年度登録年月')
    repair_history_flag   = models.BooleanField(null=True, blank=True, verbose_name='修復歴')
    inspection_expiry     = models.DateField(null=True, blank=True, verbose_name='車検有効期限')
    transmission_type     = models.CharField(max_length=10, choices=TRANSMISSION_CHOICES, blank=True, verbose_name='ミッション種別')
    registration_number   = models.CharField(max_length=20, blank=True, verbose_name='登録番号（ナンバー）')

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
# 査定申込（既存 CarAssessmentRequest を拡張）
# ---------------------------------------------------------------------------

class CarAssessmentRequest(models.Model):
    """査定申込（全チャネル統合）"""

    # 対応ステータス
    STATUS_UNTOUCHED  = '未対応'
    STATUS_NO_ANSWER  = '不通'
    STATUS_CALLBACK   = '再コール予定'
    STATUS_APPOINTMENT = '商談確定'
    STATUS_PROMOTED   = '商談昇格済'
    STATUS_CLOSED     = '成約'
    STATUS_LOST       = '見送り'

    FOLLOW_STATUS_CHOICES = [
        (STATUS_UNTOUCHED,   '未対応'),
        (STATUS_NO_ANSWER,   '不通'),
        (STATUS_CALLBACK,    '再コール予定'),
        (STATUS_APPOINTMENT, '商談確定'),
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
    gmail_message     = models.ForeignKey(
        GmailMessage,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='car_assessments',
        verbose_name='元メッセージ',
    )
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
        ]

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
    STATUS_MANAGED     = 'managed'

    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, '査定中'),
        (STATUS_CONTRACTED,  '成約'),
        (STATUS_LOST,        '不成約'),
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
    overall_rating      = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='総合評価（1〜5）')
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS, verbose_name='ステータス')
    management_status   = models.CharField(max_length=20, choices=MANAGEMENT_STATUS_CHOICES, blank=True, verbose_name='管理方針')
    cancel_reason       = models.CharField(max_length=255, blank=True, verbose_name='キャンセル理由')
    cancelled_at        = models.DateTimeField(null=True, blank=True, verbose_name='キャンセル日時')
    approved_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_assessments',
        verbose_name='承認者',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='承認日時')
    remarks     = models.TextField(blank=True, verbose_name='備考')
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
    amount_correction_flag     = models.BooleanField(default=False, verbose_name='金額訂正フラグ')
    corrected_price            = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='訂正後買取価格')
    repair_flag                = models.BooleanField(default=False, verbose_name='加修フラグ')
    repair_notes               = models.TextField(blank=True, verbose_name='加修内容')
    ownership_release_flag     = models.BooleanField(default=False, verbose_name='所有権解除フラグ')
    approved_by                = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_contracts',
        verbose_name='承認者',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='承認日時')
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
