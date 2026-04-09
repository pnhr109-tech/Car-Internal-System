from django.contrib import admin

from .models import (
    AdvancePayment,
    Assessment,
    AssessmentCheckItem,
    CarAssessmentRequest,
    ContactHistory,
    Customer,
    CustomerBankAccount,
    Document,
    DocumentTypeMaster,
    GmailMessage,
    IdentityDocument,
    OwnershipRelease,
    PurchaseContract,
    Vehicle,
    VehicleImage,
)


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------

@admin.register(GmailMessage)
class GmailMessageAdmin(admin.ModelAdmin):
    list_display    = ['received_at', 'from_address', 'subject', 'created_at']
    list_filter     = ['received_at']
    search_fields   = ['subject', 'from_address', 'message_id']
    readonly_fields = ['message_id', 'thread_id', 'created_at', 'raw_json']
    date_hierarchy  = 'received_at'
    fieldsets = (
        ('基本情報', {'fields': ('message_id', 'thread_id', 'from_address', 'to_address', 'subject')}),
        ('日時',     {'fields': ('received_at', 'created_at')}),
        ('本文',     {'fields': ('snippet', 'body_text', 'body_html'), 'classes': ('collapse',)}),
        ('生データ', {'fields': ('raw_json',), 'classes': ('collapse',)}),
    )


# ---------------------------------------------------------------------------
# 顧客
# ---------------------------------------------------------------------------

class CustomerBankAccountInline(admin.TabularInline):
    model  = CustomerBankAccount
    extra  = 0
    fields = ['bank_name', 'branch_name', 'account_type', 'account_number', 'account_holder', 'is_primary']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ['name', 'phone_number', 'email', 'address', 'created_at']
    search_fields = ['name', 'phone_number', 'email']
    inlines       = [CustomerBankAccountInline]
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('基本情報', {'fields': ('name', 'phone_number', 'email')}),
        ('住所',     {'fields': ('postal_code', 'address')}),
        ('属性',     {'fields': ('age', 'occupation', 'gender', 'family_structure'), 'classes': ('collapse',)}),
        ('システム', {'fields': ('updated_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


# ---------------------------------------------------------------------------
# 車両
# ---------------------------------------------------------------------------

class VehicleImageInline(admin.TabularInline):
    model  = VehicleImage
    extra  = 0
    fields = ['image', 'part_type', 'taken_at']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display  = ['maker', 'car_model', 'year', 'mileage', 'color', 'repair_history_flag', 'created_at']
    search_fields = ['maker', 'car_model', 'chassis_number', 'registration_number']
    list_filter   = ['maker', 'repair_history_flag', 'transmission_type']
    inlines       = [VehicleImageInline]
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('基本情報（①アポ時）',   {'fields': ('maker', 'car_model', 'year', 'mileage', 'grade', 'color', 'displacement', 'remarks')}),
        ('詳細情報（②商談時）',   {'fields': ('chassis_number', 'first_registration_date', 'repair_history_flag', 'inspection_expiry', 'transmission_type', 'registration_number')}),
        ('システム',              {'fields': ('updated_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


# ---------------------------------------------------------------------------
# 査定申込
# ---------------------------------------------------------------------------

@admin.register(CarAssessmentRequest)
class CarAssessmentRequestAdmin(admin.ModelAdmin):
    list_display  = ['application_number', 'application_datetime', 'channel_type', 'customer_name', 'phone_number', 'follow_status', 'assigned_to', 'maker', 'car_model']
    list_filter   = ['channel_type', 'follow_status', 'application_datetime']
    search_fields = ['application_number', 'customer_name', 'phone_number', 'email', 'maker', 'car_model']
    readonly_fields = ['application_number', 'created_at', 'updated_at']
    date_hierarchy = 'application_datetime'
    raw_id_fields  = ['customer', 'vehicle', 'assigned_to', 'gmail_message']
    fieldsets = (
        ('申込情報',   {'fields': ('application_number', 'application_datetime', 'channel_type', 'external_service_id', 'referral_name', 'reservation_datetime', 'desired_sale_timing')}),
        ('顧客情報',   {'fields': ('customer', 'customer_name', 'phone_number', 'email', 'postal_code', 'address')}),
        ('車両情報',   {'fields': ('vehicle', 'maker', 'car_model', 'year', 'mileage')}),
        ('営業対応',   {'fields': ('assigned_to', 'sales_owner_name', 'sales_assigned_at', 'follow_status', 'call_count', 'cancel_reason', 'sales_note', 'status_updated_at', 'status_updated_by')}),
        ('システム情報', {'fields': ('gmail_message', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


# ---------------------------------------------------------------------------
# 査定（商談）
# ---------------------------------------------------------------------------

class AssessmentCheckItemInline(admin.TabularInline):
    model  = AssessmentCheckItem
    extra  = 0
    fields = ['check_type', 'description']


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display  = ['assessment_request', 'customer', 'vehicle', 'assigned_to', 'status', 'assessment_price', 'approved_by', 'created_at']
    list_filter   = ['status', 'management_status']
    search_fields = ['customer__name', 'customer__phone_number', 'vehicle__maker', 'vehicle__car_model']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields   = ['assessment_request', 'customer', 'vehicle', 'assigned_to', 'approved_by', 'updated_by']
    inlines         = [AssessmentCheckItemInline]
    fieldsets = (
        ('基本情報',   {'fields': ('assessment_request', 'customer', 'vehicle', 'assigned_to')}),
        ('査定内容',   {'fields': ('assessment_datetime', 'assessment_price', 'market_price', 'overall_rating')}),
        ('ステータス', {'fields': ('status', 'management_status', 'cancel_reason', 'cancelled_at')}),
        ('承認',       {'fields': ('approved_by', 'approved_at')}),
        ('備考',       {'fields': ('remarks',)}),
        ('システム',   {'fields': ('updated_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


# ---------------------------------------------------------------------------
# 買取契約
# ---------------------------------------------------------------------------

class DocumentInline(admin.TabularInline):
    model  = Document
    extra  = 0
    fields = ['document_type', 'status', 'later_send_status', 'received_date']


class IdentityDocumentInline(admin.TabularInline):
    model  = IdentityDocument
    extra  = 0
    fields = ['doc_type', 'verified_at', 'verified_by', 'file']


class AdvancePaymentInline(admin.TabularInline):
    model  = AdvancePayment
    extra  = 0
    fields = ['expected_amount', 'payment_date', 'status', 'approved_by']


@admin.register(PurchaseContract)
class PurchaseContractAdmin(admin.ModelAdmin):
    list_display  = ['assessment', 'customer', 'vehicle', 'contract_date', 'purchase_price_incl_tax', 'status', 'approved_by']
    list_filter   = ['status', 'contract_date', 'ownership_release_flag', 'repair_flag']
    search_fields = ['customer__name', 'customer__phone_number', 'vehicle__maker', 'vehicle__car_model']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields   = ['assessment', 'customer', 'vehicle', 'assigned_to', 'approved_by', 'updated_by']
    inlines         = [DocumentInline, IdentityDocumentInline, AdvancePaymentInline]
    fieldsets = (
        ('基本情報',     {'fields': ('assessment', 'customer', 'vehicle', 'assigned_to', 'contract_date')}),
        ('金額',         {'fields': ('purchase_price_excl_tax', 'tax_amount', 'purchase_price_incl_tax', 'amount_correction_flag', 'corrected_price')}),
        ('予定日',       {'fields': ('payment_scheduled_date', 'auction_scheduled_date')}),
        ('特記事項',     {'fields': ('repair_flag', 'repair_notes', 'ownership_release_flag')}),
        ('ステータス',   {'fields': ('status', 'cancel_reason', 'cancelled_at')}),
        ('承認',         {'fields': ('approved_by', 'approved_at')}),
        ('備考',         {'fields': ('remarks',)}),
        ('システム',     {'fields': ('updated_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(OwnershipRelease)
class OwnershipReleaseAdmin(admin.ModelAdmin):
    list_display  = ['contract', 'pattern', 'status', 'dealer_doc_sent_date', 'debt_transfer_date', 'dealer_doc_returned_date']
    list_filter   = ['pattern', 'status']
    raw_id_fields = ['contract']


@admin.register(DocumentTypeMaster)
class DocumentTypeMasterAdmin(admin.ModelAdmin):
    list_display = ['name', 'required_flag', 'description']
    list_filter  = ['required_flag']


# ---------------------------------------------------------------------------
# 連絡履歴
# ---------------------------------------------------------------------------

@admin.register(ContactHistory)
class ContactHistoryAdmin(admin.ModelAdmin):
    list_display  = ['assessment_request', 'customer', 'recorded_by', 'contacted_at', 'contact_method']
    list_filter   = ['contact_method', 'contacted_at']
    search_fields = ['assessment_request__customer_name', 'content']
    raw_id_fields = ['assessment_request', 'customer', 'recorded_by']
    readonly_fields = ['created_at']
