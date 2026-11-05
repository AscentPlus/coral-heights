from django.db import models
from django.contrib.auth.models import User


class StaffProfile(models.Model):
    ACCESS_WEBSITE = 'website'
    ACCESS_BOOKINGS = 'bookings'
    ACCESS_BOTH = 'both'

    ACCESS_CHOICES = [
        (ACCESS_WEBSITE, 'Website Content Only'),
        (ACCESS_BOOKINGS, 'Bookings & Guests Only'),
        (ACCESS_BOTH, 'Website + Bookings'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='staff_profile')
    access_level = models.CharField(
        max_length=20, choices=ACCESS_CHOICES, default=ACCESS_BOOKINGS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'

    def __str__(self):
        return f"{self.user.username} ({self.get_access_level_display()})"
