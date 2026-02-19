from django.contrib import admin
from .models import GmailMessage, CarAssessmentRequest


@admin.register(GmailMessage)
class GmailMessageAdmin(admin.ModelAdmin):
    list_display = ['received_at', 'from_address', 'to_address', 'subject', 'created_at']
    list_filter = ['received_at', 'from_address', 'to_address']
    search_fields = ['subject', 'from_address', 'to_address', 'message_id']
    readonly_fields = ['message_id', 'thread_id', 'created_at', 'raw_json']
    date_hierarchy = 'received_at'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('message_id', 'thread_id', 'from_address', 'to_address', 'subject')
        }),
        ('日時', {
            'fields': ('received_at', 'created_at')
        }),
        ('本文', {
            'fields': ('snippet', 'body_text', 'body_html'),
            'classes': ('collapse',)
        }),
        ('生データ', {
            'fields': ('raw_json',),
            'classes': ('collapse',)
        }),
    )


@admin.register(CarAssessmentRequest)
class CarAssessmentRequestAdmin(admin.ModelAdmin):
    list_display = ['application_number', 'application_datetime', 'customer_name', 'sales_owner_name', 'follow_status', 'phone_number', 'maker', 'car_model', 'created_at']
    list_filter = ['application_datetime', 'maker', 'desired_sale_timing', 'follow_status']
    search_fields = ['application_number', 'customer_name', 'phone_number', 'email', 'maker', 'car_model', 'sales_owner_name']
    readonly_fields = ['application_number', 'created_at', 'updated_at', 'gmail_message']
    date_hierarchy = 'application_datetime'
    
    fieldsets = (
        ('申込情報', {
            'fields': ('application_number', 'application_datetime', 'desired_sale_timing')
        }),
        ('車両情報', {
            'fields': ('maker', 'car_model', 'year', 'mileage')
        }),
        ('顧客情報', {
            'fields': ('customer_name', 'phone_number', 'postal_code', 'address', 'email')
        }),
        ('営業対応', {
            'fields': ('sales_owner_name', 'sales_assigned_at', 'follow_status', 'sales_note', 'status_updated_at', 'status_updated_by')
        }),
        ('システム情報', {
            'fields': ('gmail_message', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
