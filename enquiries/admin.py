from django.contrib import admin
from .models import Enquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'contact_name', 'contact_phone', 'function_type',
                    'preferred_date', 'guest_count', 'status', 'created_at')
    list_filter = ('status', 'function_type', 'preferred_date')
    search_fields = ('contact_name', 'contact_phone',
                     'menu_requirements', 'notes', 'staff_remarks')
    ordering = ('-created_at',)
