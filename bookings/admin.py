from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from .models import Guest, Booking, PhoneOTP


from .services import mark_booking_departed


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'created_at')
    search_fields = ('name', 'phone', 'email')
    ordering = ('-created_at',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest', 'room', 'check_in', 'check_out', 'actual_check_out',
                    'adults', 'children', 'status', 'total_amount', 'receipt_link', 'created_at')
    list_filter = ('status', 'check_in', 'check_out')
    search_fields = ('guest__name', 'guest__phone', 'room__room_number')
    readonly_fields = ('access_token', 'receipt_link', 'created_at')
    ordering = ('-created_at',)
    actions = ['mark_guest_departed']

    @admin.action(description="Mark guest departed (free room now)")
    def mark_guest_departed(self, request, queryset):
        success_count = 0
        skipped_count = 0

        for booking in queryset:
            success, msg = mark_booking_departed(booking)
            if success:
                success_count += 1
            else:
                skipped_count += 1

        if success_count:
            self.message_user(
                request,
                f"{success_count} booking(s) marked as departed and room(s) freed.",
                level=messages.SUCCESS
            )

        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} selected booking(s) were skipped. Only confirmed bookings that have already checked in can be marked as departed.",
                level=messages.WARNING
            )

    def receipt_link(self, obj):
        if obj.id and obj.status == Booking.STATUS_CONFIRMED:
            url = reverse('bookings:receipt', kwargs={
                          'booking_id': obj.id, 'token': obj.access_token or 'staff'})
            return format_html('<a href="{}" target="_blank" style="font-weight: bold; color: #115e59;">View / Print Receipt ↗</a>', url)
        return "-"
    receipt_link.short_description = 'Receipt'


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'code', 'is_verified',
                    'attempts', 'created_at', 'expires_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('phone', 'code')
    ordering = ('-created_at',)
