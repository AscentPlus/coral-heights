from django import forms
from django.utils import timezone
from .models import Enquiry


class EnquiryForm(forms.ModelForm):
    class Meta:
        model = Enquiry
        fields = [
            'function_type',
            'preferred_date',
            'guest_count',
            'menu_requirements',
            'contact_name',
            'contact_phone',
            'notes',
        ]
        widgets = {
            'preferred_date': forms.DateInput(attrs={'type': 'date'}),
            'guest_count': forms.NumberInput(attrs={'min': '1'}),
            'menu_requirements': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_contact_phone(self):
        phone = self.cleaned_data.get('contact_phone', '').strip()
        if not phone.isdigit() or len(phone) != 10:
            raise forms.ValidationError(
                "Phone number must be exactly 10 digits.")
        return phone

    def clean_preferred_date(self):
        pref_date = self.cleaned_data.get('preferred_date')
        if pref_date and pref_date < timezone.now().date():
            raise forms.ValidationError(
                "Preferred date cannot be in the past.")
        return pref_date

    def clean_guest_count(self):
        count = self.cleaned_data.get('guest_count')
        if count is not None and count <= 0:
            raise forms.ValidationError(
                "Expected number of guests must be at least 1.")
        return count
