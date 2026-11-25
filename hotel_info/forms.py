from django import forms
from .models import (
    HotelInfo, RestaurantInfo, MenuCategory, MenuItem,
    NearbyPlace, ChatFAQ
)

input_style = "w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20 bg-white"
textarea_style = "w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20 bg-white"
select_style = "w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20 bg-white"
checkbox_style = "w-4 h-4 text-teal-800 rounded border-slate-300 focus:ring-teal-700"


class HotelInfoForm(forms.ModelForm):
    class Meta:
        model = HotelInfo
        fields = [
            'check_in_time', 'check_out_time', 'address_note',
            'parking_info', 'wifi_info', 'payment_methods',
            'languages_spoken', 'pet_policy', 'extra_notes', 'rate_note'
        ]
        widgets = {
            'check_in_time': forms.TextInput(attrs={'class': input_style}),
            'check_out_time': forms.TextInput(attrs={'class': input_style}),
            'address_note': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'parking_info': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'wifi_info': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'payment_methods': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'languages_spoken': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'pet_policy': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'extra_notes': forms.Textarea(attrs={'class': textarea_style, 'rows': 3}),
            'rate_note': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
        }


class RestaurantInfoForm(forms.ModelForm):
    class Meta:
        model = RestaurantInfo
        fields = [
            'name', 'cuisine_description', 'breakfast_hours',
            'lunch_hours', 'dinner_hours', 'thattukada_hours',
            'room_service_info',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': input_style}),
            'cuisine_description': forms.Textarea(attrs={'class': textarea_style, 'rows': 3}),
            'breakfast_hours': forms.TextInput(attrs={'class': input_style}),
            'lunch_hours': forms.TextInput(attrs={'class': input_style}),
            'dinner_hours': forms.TextInput(attrs={'class': input_style}),
            'thattukada_hours': forms.TextInput(attrs={'class': input_style}),
            'room_service_info': forms.TextInput(attrs={'class': input_style}),
        }


class MenuCategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ['name', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_style}),
            'display_order': forms.NumberInput(attrs={'class': input_style}),
        }


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['category', 'name', 'description', 'price', 'is_veg', 'is_available', 'display_order']
        widgets = {
            'category': forms.Select(attrs={'class': select_style}),
            'name': forms.TextInput(attrs={'class': input_style}),
            'description': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'price': forms.NumberInput(attrs={'class': input_style, 'step': '0.01'}),
            'is_veg': forms.CheckboxInput(attrs={'class': checkbox_style}),
            'is_available': forms.CheckboxInput(attrs={'class': checkbox_style}),
            'display_order': forms.NumberInput(attrs={'class': input_style}),
        }


class NearbyPlaceForm(forms.ModelForm):
    class Meta:
        model = NearbyPlace
        fields = ['place_type', 'name', 'distance_km', 'travel_time', 'directions_note', 'display_order']
        widgets = {
            'place_type': forms.Select(attrs={'class': select_style}),
            'name': forms.TextInput(attrs={'class': input_style}),
            'distance_km': forms.NumberInput(attrs={'class': input_style, 'step': '0.01'}),
            'travel_time': forms.TextInput(attrs={'class': input_style}),
            'directions_note': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'display_order': forms.NumberInput(attrs={'class': input_style}),
        }


class ChatFAQForm(forms.ModelForm):
    class Meta:
        model = ChatFAQ
        fields = ['question', 'keywords', 'answer', 'is_active', 'display_order']
        widgets = {
            'question': forms.TextInput(attrs={'class': input_style}),
            'keywords': forms.Textarea(attrs={'class': textarea_style, 'rows': 2}),
            'answer': forms.Textarea(attrs={'class': textarea_style, 'rows': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': checkbox_style}),
            'display_order': forms.NumberInput(attrs={'class': input_style}),
        }

