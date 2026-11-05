from django import forms
from django.contrib.auth.models import User
from .models import StaffProfile


class StaffLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Username',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20 text-sm'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20 text-sm'
        })
    )


class StaffCreateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'New staff username',
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Temporary password',
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20'
        })
    )
    access_bookings = forms.BooleanField(
        required=False,
        initial=True,
        label="Bookings & Enquiries",
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-teal-800 rounded border-slate-300 focus:ring-teal-700'
        })
    )
    access_website = forms.BooleanField(
        required=False,
        initial=False,
        label="Website Management",
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-teal-800 rounded border-slate-300 focus:ring-teal-700'
        })
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "A user with this username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        bookings = cleaned_data.get('access_bookings')
        website = cleaned_data.get('access_website')

        if not bookings and not website:
            raise forms.ValidationError(
                "Select at least one section for staff access permissions.")

        if bookings and website:
            cleaned_data['access_level'] = StaffProfile.ACCESS_BOTH
        elif website:
            cleaned_data['access_level'] = StaffProfile.ACCESS_WEBSITE
        else:
            cleaned_data['access_level'] = StaffProfile.ACCESS_BOOKINGS

        return cleaned_data

    def save(self):
        username = self.cleaned_data['username']
        password = self.cleaned_data['password']
        access_level = self.cleaned_data['access_level']

        user = User.objects.create_user(
            username=username,
            password=password,
            is_staff=False,
            is_superuser=False,
            is_active=True
        )

        profile = StaffProfile.objects.create(
            user=user,
            access_level=access_level
        )

        return user


# --- Website Content Management Forms ---
from django.utils.text import slugify
from content.models import RoomType, Facility, Attraction, ContactInformation

input_style = "w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20 bg-white"
textarea_style = "w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20 bg-white"
file_style = "w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-teal-50 file:text-teal-900 hover:file:bg-teal-100"


class RoomTypeForm(forms.ModelForm):
    slug = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Auto-generated from name if left blank',
            'class': input_style
        })
    )

    class Meta:
        model = RoomType
        fields = [
            'name', 'slug', 'short_description', 'long_description',
            'base_price_per_night', 'max_occupancy', 'bed_type',
            'image', 'image_url', 'display_order'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': input_style, 'placeholder': 'e.g. Executive Suite'}),
            'short_description': forms.Textarea(attrs={'class': textarea_style, 'rows': 2, 'placeholder': 'Short summary for room cards'}),
            'long_description': forms.Textarea(attrs={'class': textarea_style, 'rows': 4, 'placeholder': 'Detailed modal description'}),
            'base_price_per_night': forms.NumberInput(attrs={'class': input_style, 'step': '0.01'}),
            'max_occupancy': forms.NumberInput(attrs={'class': input_style, 'min': '1'}),
            'bed_type': forms.TextInput(attrs={'class': input_style, 'placeholder': 'e.g. King Bed'}),
            'image': forms.FileInput(attrs={'class': file_style}),
            'image_url': forms.TextInput(attrs={'class': input_style, 'placeholder': 'Fallback external image URL (optional)'}),
            'display_order': forms.NumberInput(attrs={'class': input_style}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        name = self.cleaned_data.get('name', '').strip()
        if not slug and name:
            slug = slugify(name)

        # Ensure slug is unique if creating or changing
        instance = getattr(self, 'instance', None)
        qs = RoomType.objects.filter(slug=slug)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise forms.ValidationError("A room type with this slug already exists.")
        return slug


class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ['name', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_style, 'placeholder': 'e.g. Free High-Speed Wi-Fi'}),
            'display_order': forms.NumberInput(attrs={'class': input_style}),
        }


class AttractionForm(forms.ModelForm):
    class Meta:
        model = Attraction
        fields = ['name', 'description', 'distance_label', 'image', 'image_url', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_style, 'placeholder': 'e.g. Ambalapuzha Sri Krishna Temple'}),
            'description': forms.Textarea(attrs={'class': textarea_style, 'rows': 3, 'placeholder': 'Brief description of attraction'}),
            'distance_label': forms.TextInput(attrs={'class': input_style, 'placeholder': 'e.g. 1.5 km'}),
            'image': forms.FileInput(attrs={'class': file_style}),
            'image_url': forms.TextInput(attrs={'class': input_style, 'placeholder': 'Fallback external image URL (optional)'}),
            'display_order': forms.NumberInput(attrs={'class': input_style}),
        }


class ContactInformationForm(forms.ModelForm):
    class Meta:
        model = ContactInformation
        fields = [
            'primary_phone', 'landline_1', 'landline_2', 'whatsapp_number',
            'email', 'facebook_url', 'instagram_url',
            'address_line_1', 'address_line_2', 'address_line_3'
        ]
        widgets = {
            'primary_phone': forms.TextInput(attrs={'class': input_style}),
            'landline_1': forms.TextInput(attrs={'class': input_style}),
            'landline_2': forms.TextInput(attrs={'class': input_style}),
            'whatsapp_number': forms.TextInput(attrs={'class': input_style}),
            'email': forms.EmailInput(attrs={'class': input_style}),
            'facebook_url': forms.URLInput(attrs={'class': input_style}),
            'instagram_url': forms.URLInput(attrs={'class': input_style}),
            'address_line_1': forms.TextInput(attrs={'class': input_style}),
            'address_line_2': forms.TextInput(attrs={'class': input_style}),
            'address_line_3': forms.TextInput(attrs={'class': input_style}),
        }

