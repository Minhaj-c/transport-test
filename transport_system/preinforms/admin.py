from django.contrib import admin
from django.db.models import Count, Sum, Q  
from datetime import date  
from .models import PreInform


@admin.register(PreInform)
class PreInformAdmin(admin.ModelAdmin):
    """
    Admin configuration for PreInform model
    
    🔥 AUTO-ACCEPTANCE: No approval workflow needed
    Admin can monitor all pre-informs and cancel fraudulent ones
    """
    list_display = (
        'id',
        'user',
        'route',
        'date_of_travel',
        'desired_time',
        'boarding_stop',
        'dropoff_stop',
        'passenger_count',
        'status',
        'created_at'
    )
    
    list_filter = (
        'status', 
        'date_of_travel', 
        'route', 
        'created_at',
        'passenger_count'
    )
    
    search_fields = (
        'user__email',
        'user__phone',
        'route__number',
        'route__name',
        'boarding_stop__name',
        'dropoff_stop__name'
    )
    
    date_hierarchy = 'date_of_travel'
    ordering = ('-created_at',)
    
    # Allow editing status from list view
    list_editable = ('status',)
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Travel Details', {
            'fields': (
                'route', 
                'boarding_stop', 
                'dropoff_stop',
                'date_of_travel', 
                'desired_time', 
                'passenger_count'
            )
        }),
        ('Status', {
            'fields': ('status',),
            'description': 'Pre-informs are auto-accepted (status: noted). Change to cancelled if fraudulent.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    # 🔥 ADMIN ACTIONS: Only cancel action (no approve/reject needed)
    actions = ['mark_as_cancelled', 'mark_as_completed']
    
    def mark_as_cancelled(self, request, queryset):
        """
        Cancel pre-informs (e.g., duplicate or fraudulent submissions)
        """
        # Only cancel 'noted' pre-informs
        updated = queryset.filter(status='noted').update(status='cancelled')
        
        if updated:
            self.message_user(
                request, 
                f"✅ Cancelled {updated} pre-inform(s)."
            )
        else:
            self.message_user(
                request,
                "⚠️ No pre-informs were cancelled. Only 'noted' status can be cancelled.",
                level='warning'
            )
    
    mark_as_cancelled.short_description = "Cancel selected pre-informs"
    
    def mark_as_completed(self, request, queryset):
        """
        Mark pre-informs as completed (journey finished)
        """
        updated = queryset.filter(status='noted').update(status='completed')
        
        if updated:
            self.message_user(
                request,
                f"✅ Marked {updated} pre-inform(s) as completed."
            )
        else:
            self.message_user(
                request,
                "⚠️ No pre-informs were updated.",
                level='warning'
            )
    
    mark_as_completed.short_description = "Mark as completed"
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related(
            'user', 
            'route', 
            'boarding_stop',
            'dropoff_stop'
        )
    
    # 🔥 CUSTOM DISPLAY: Show summary in admin
    def changelist_view(self, request, extra_context=None):
        """
        Add summary statistics to admin list view
        """
        extra_context = extra_context or {}
        
        # Get today
        today = date.today()
        
        # 🔥 FIXED: Use Q from django.db.models
        stats = PreInform.objects.aggregate(
            total=Count('id'),
            noted=Count('id', filter=Q(status='noted')),
            today_count=Count('id', filter=Q(date_of_travel=today)),
            total_passengers=Sum('passenger_count')
        )
        
        extra_context['summary'] = {
            'total_preinforms': stats['total'] or 0,
            'active_preinforms': stats['noted'] or 0,
            'today_preinforms': stats['today_count'] or 0,
            'total_passengers': stats['total_passengers'] or 0,
        }
        
        return super().changelist_view(request, extra_context=extra_context)


# 🔥 OPTIONAL: Add inline admin for debugging
class PreInformInline(admin.TabularInline):
    """
    Inline admin to show pre-informs in User or Route admin
    """
    model = PreInform
    extra = 0
    fields = (
        'date_of_travel',
        'desired_time',
        'boarding_stop',
        'dropoff_stop',
        'passenger_count',
        'status'
    )
    readonly_fields = fields
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False