from django.contrib import admin
from .models import Zone

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'district')
    search_fields = ('name', 'code', 'district')
    ordering = ('name',)
