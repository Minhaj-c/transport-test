"""
User Admin Configuration
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Custom admin for CustomUser model
    """

    # Display configuration
    list_display = ('email', 'role', 'zone', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('role', 'zone', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    # Fields shown in user edit page
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        
        (_('Personal info'), {
            'fields': ('first_name', 'last_name')
        }),

        (_('Role & Zone'), {
            'fields': ('role', 'zone')
        }),

        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            ),
        }),

        (_('Important dates'), {
            'fields': ('last_login', 'date_joined'),
        }),
    )

    # Fields shown when creating user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'password1',
                'password2',
                'role',
                'zone',
                'first_name',
                'last_name',
            ),
        }),
    )

    # Readonly fields
    readonly_fields = ('date_joined', 'last_login')

    # Filter horizontal for permissions
    filter_horizontal = ('groups', 'user_permissions')
