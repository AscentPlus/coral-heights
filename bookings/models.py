from django.db import models
from django.utils import timezone
from content.models import Room


class Guest(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Guest'
        verbose_name_plural = 'Guests'

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Booking(models.Model):
    """
    Booking model for physical Room instances.
    """
    STATUS_HELD = 'held'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_HELD, 'Held'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    room = models.ForeignKey(
        Room, on_delete=models.PROTECT, related_name='bookings')
    guest = models.ForeignKey(
        Guest, on_delete=models.PROTECT, related_name='bookings')
    check_in = models.DateField()
    check_out = models.DateField()
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_HELD)
    hold_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Only set for status=held; null for confirmed/cancelled/completed")
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    access_token = models.CharField(
        max_length=40, unique=True, blank=True, editable=False)
    actual_check_out = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the guest actually departed — set automatically when a booking is marked completed. Used for reporting only; availability already treats any 'completed' booking as non-blocking regardless of this field."
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'

    def save(self, *args, **kwargs):
        if not self.access_token:
            import secrets
            self.access_token = secrets.token_urlsafe(24)[:40]
        super().save(*args, **kwargs)

    @property
    def reference(self):
        return f"CH-{self.id:05d}"

    @property
    def is_overdue(self):
        today = timezone.now().date()
        return self.status == self.STATUS_CONFIRMED and self.check_out < today and self.actual_check_out is None

    @property
    def hold_time_remaining(self):
        """
        Returns a human-readable string indicating when the hold expires,
        e.g. "Held until 3:47 PM" or "Expires in 8 min".
        Returns None if the booking is not held or the hold has expired.
        """
        if self.status != self.STATUS_HELD or not self.hold_expires_at:
            return None
        now = timezone.now()
        delta = self.hold_expires_at - now
        total_secs = int(delta.total_seconds())
        if total_secs <= 0:
            return None
        minutes = total_secs // 60
        if minutes < 1:
            return f"Expires in {total_secs}s"
        if minutes < 60:
            return f"Expires in {minutes} min"
        # Format as a clock time if more than an hour away
        local_expiry = timezone.localtime(self.hold_expires_at)
        return f"Held until {local_expiry.strftime('%-I:%M %p')}"

    def __str__(self):
        return f"Booking #{self.id} — Room {self.room.room_number} ({self.guest.name})"


class PhoneOTP(models.Model):
    phone = models.CharField(max_length=20)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Phone OTP'
        verbose_name_plural = 'Phone OTPs'

    def __str__(self):
        return f"OTP for {self.phone} ({self.code})"
