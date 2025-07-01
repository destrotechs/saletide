from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'company', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'role', 'company__name')
    ordering = ('email',)
    list_filter = ('role', 'company', 'is_staff', 'is_active')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('username', 'first_name', 'last_name', 'company', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'first_name', 'last_name',
                'password1', 'password2', 'company', 'role', 'is_staff', 'is_active'
            )}
        ),
    )

admin.site.register(CustomUser, CustomUserAdmin)
