from django.db import models


class Enquiry(models.Model):
    FUNCTION_BIRTHDAY = 'birthday'
    FUNCTION_WEDDING = 'wedding'
    FUNCTION_CORPORATE = 'corporate'
    FUNCTION_OTHER = 'other'

    FUNCTION_CHOICES = [
        (FUNCTION_BIRTHDAY, 'Birthday Party'),
        (FUNCTION_WEDDING, 'Wedding / Reception'),
        (FUNCTION_CORPORATE, 'Corporate Event'),
        (FUNCTION_OTHER, 'Other Event'),
    ]

    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_CONTACTED, 'Contacted'),
        (STATUS_CLOSED, 'Closed'),
    ]

    function_type = models.CharField(
        max_length=30, choices=FUNCTION_CHOICES, default=FUNCTION_OTHER)
    preferred_date = models.DateField()
    guest_count = models.PositiveIntegerField()
    menu_requirements = models.TextField(
        blank=True, help_text="Specific food / menu requests")
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    staff_remarks = models.TextField(
        blank=True, default='', verbose_name="Staff Remarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Catering & Event Enquiry'
        verbose_name_plural = 'Catering & Event Enquiries'

    def __str__(self):
        return f"{self.get_function_type_display()} on {self.preferred_date} ({self.contact_name})"
