from django.contrib import admin
from .models import RoomType, Room, Facility, Attraction, ContactInformation


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'base_price_per_night',
                    'max_occupancy', 'bed_type', 'display_order', 'get_room_count')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('display_order',)
    inlines = [RoomInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'short_description', 'long_description',
                       'base_price_per_night', 'max_occupancy', 'bed_type',
                       'image', 'image_url', 'display_order')
        }),
    )

    def get_room_count(self, obj):
        return obj.rooms.count()
    get_room_count.short_description = 'Total Inventory Units'


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type')
    list_filter = ('room_type',)
    search_fields = ('room_number',)


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order')
    ordering = ('display_order',)


@admin.register(Attraction)
class AttractionAdmin(admin.ModelAdmin):
    list_display = ('name', 'distance_label', 'display_order')
    ordering = ('display_order',)
    fields = ('name', 'description', 'distance_label', 'image', 'image_url', 'display_order')



@admin.register(ContactInformation)
class ContactInformationAdmin(admin.ModelAdmin):
    list_display = ('primary_phone', 'landline_1',
                    'landline_2', 'email', 'whatsapp_number')
    fieldsets = (
        ('Contact Numbers', {
            'fields': ('primary_phone', 'landline_1', 'landline_2', 'whatsapp_number')
        }),
        ('Email & Address', {
            'fields': ('email', 'address_line_1', 'address_line_2', 'address_line_3')
        }),
        ('Social Media Profiles', {
            'fields': ('facebook_url', 'instagram_url')
        }),
    )

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
