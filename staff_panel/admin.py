from django.contrib import admin
from .models import StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'access_level', 'created_at')
    list_filter = ('access_level', 'created_at')
    search_fields = ('user__username', 'user__email')
    ordering = ('-created_at',)
