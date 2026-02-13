from django.db import models


class GmailMessage(models.Model):
    """Gmail メッセージを保存するモデル（重複防止対応）"""
    
    # Gmail固有のID（重複防止の要）
    message_id = models.CharField(max_length=255, unique=True, db_index=True, verbose_name='メッセージID')
    thread_id = models.CharField(max_length=255, db_index=True, verbose_name='スレッドID')
    
    # メール基本情報
    from_address = models.EmailField(max_length=255, verbose_name='送信元')
    to_address = models.EmailField(max_length=255, verbose_name='宛先')
    subject = models.CharField(max_length=500, verbose_name='件名')
    
    # 日時
    received_at = models.DateTimeField(db_index=True, verbose_name='受信日時')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='取り込み日時')
    
    # 本文情報
    snippet = models.TextField(blank=True, null=True, verbose_name='スニペット')
    body_text = models.TextField(blank=True, null=True, verbose_name='本文（テキスト）')
    body_html = models.TextField(blank=True, null=True, verbose_name='本文（HTML）')
    
    # 生データ（トラブルシュート用）
    raw_json = models.JSONField(blank=True, null=True, verbose_name='Gmail API レスポンス')
    
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


class CarAssessmentRequest(models.Model):
    """かんたん車査定ガイドの申込情報（メール本文から抽出）"""
    
    # 申込情報（一意性制約）
    application_number = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='お申込番号')
    application_datetime = models.DateTimeField(verbose_name='お申込日時')
    desired_sale_timing = models.CharField(max_length=100, blank=True, verbose_name='希望売却時期')
    
    # 車両情報
    maker = models.CharField(max_length=100, blank=True, verbose_name='メーカー名')
    car_model = models.CharField(max_length=100, blank=True, verbose_name='車種名')
    year = models.CharField(max_length=100, blank=True, verbose_name='年式')
    mileage = models.CharField(max_length=100, blank=True, verbose_name='走行距離')
    
    # 顧客情報
    customer_name = models.CharField(max_length=100, verbose_name='お名前')
    phone_number = models.CharField(max_length=20, verbose_name='電話番号')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='郵便番号')
    address = models.CharField(max_length=255, blank=True, verbose_name='住所')
    email = models.EmailField(max_length=255, blank=True, verbose_name='メールアドレス')
    
    # 関連メール（参照用）
    gmail_message = models.ForeignKey(
        GmailMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='car_assessments',
        verbose_name='元メッセージ'
    )
    
    # 取り込み日時
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='取り込み日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    
    class Meta:
        db_table = 'car_assessment_requests'
        verbose_name = '車査定申込'
        verbose_name_plural = '車査定申込'
        ordering = ['-application_datetime']
        indexes = [
            models.Index(fields=['-application_datetime'], name='idx_app_datetime'),
            models.Index(fields=['customer_name'], name='idx_customer_name'),
            models.Index(fields=['phone_number'], name='idx_phone_number'),
        ]
    
    def __str__(self):
        return f"{self.application_number} - {self.customer_name} ({self.maker} {self.car_model})"
