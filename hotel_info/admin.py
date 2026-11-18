from django.contrib import admin
from .models import (
    HotelInfo, RestaurantInfo, MenuCategory, MenuItem,
    NearbyPlace, ChatFAQ, UnansweredQuestion
)


@admin.register(HotelInfo)
class HotelInfoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'check_in_time', 'check_out_time')

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(RestaurantInfo)
class RestaurantInfoAdmin(admin.ModelAdmin):
    list_display = ('name', 'breakfast_hours', 'lunch_hours', 'dinner_hours')

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 1


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'item_count')
    ordering = ('display_order', 'name')
    inlines = [MenuItemInline]

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_veg', 'is_available', 'display_order')
    list_filter = ('category', 'is_veg', 'is_available')
    search_fields = ('name', 'description')
    ordering = ('category', 'display_order', 'name')


@admin.register(NearbyPlace)
class NearbyPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'place_type', 'distance_km', 'travel_time', 'display_order')
    list_filter = ('place_type',)
    search_fields = ('name', 'directions_note')
    ordering = ('display_order', 'distance_km')


@admin.register(ChatFAQ)
class ChatFAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('question', 'keywords', 'answer')
    ordering = ('display_order', 'id')


@admin.register(UnansweredQuestion)
class UnansweredQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'count', 'first_asked', 'last_asked', 'is_handled')
    list_filter = ('is_handled',)
    search_fields = ('text',)
    ordering = ('-last_asked',)
    readonly_fields = ('first_asked', 'last_asked')

