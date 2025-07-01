from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Company, Employee, EmployeeCommissionSetting, EmployeeCommission,
    EmployeeRemuneration, EmployeeLeave, EmployeeDeduction
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'subscription_plan', 'subscription_fee', 'is_active', 'created_at']
    list_filter = ['subscription_plan', 'is_active', 'is_deleted', 'created_at']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['created_at']
    filter_horizontal = ['directors']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'email', 'phone', 'address', 'company_logo')
        }),
        ('Subscription Details', {
            'fields': ('subscription_plan', 'subscription_fee')
        }),
        ('Status', {
            'fields': ('is_active', 'is_deleted', 'date_deleted')
        }),
        ('Relationships', {
            'fields': ('directors',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'position', 'date_employed', 'salary', 'is_deleted', 'created_at']
    list_filter = ['company', 'is_deleted', 'date_employed', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'position']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'user', 'position')
        }),
        ('Employment Details', {
            'fields': ('date_employed', 'salary')
        }),
        ('Status', {
            'fields': ('is_deleted', 'date_deleted')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmployeeCommissionSetting)
class EmployeeCommissionSettingAdmin(admin.ModelAdmin):
    list_display = ['employee', 'service', 'commission_percentage', 'created_at']
    list_filter = ['employee__company', 'created_at']
    search_fields = ['employee__user__email', 'service__name']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee__user', 'service')


@admin.register(EmployeeCommission)
class EmployeeCommissionAdmin(admin.ModelAdmin):
    list_display = ['sale_item', 'employee', 'commission_amount', 'paid', 'date_paid', 'date_calculate']
    list_filter = ['paid', 'date_paid', 'date_calculate', 'employee__company']
    search_fields = ['sale__id', 'employee__user__email']
    readonly_fields = ['date_calculate']

    actions = ['mark_as_paid', 'mark_as_unpaid']

    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        queryset.update(paid=True, date_paid=timezone.now())
        self.message_user(request, f"Marked {queryset.count()} commissions as paid.")

    mark_as_paid.short_description = "Mark selected commissions as paid"

    def mark_as_unpaid(self, request, queryset):
        queryset.update(paid=False, date_paid=None)
        self.message_user(request, f"Marked {queryset.count()} commissions as unpaid.")

    mark_as_unpaid.short_description = "Mark selected commissions as unpaid"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sale_item', 'employee__user')


@admin.register(EmployeeRemuneration)
class EmployeeRemunerationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'remuneration_type', 'name', 'amount', 'currency', 'created_at']
    list_filter = ['remuneration_type', 'currency', 'employee__company', 'created_at']
    search_fields = ['employee__user__email', 'name', 'remuneration_type']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('employee', 'remuneration_type', 'name')
        }),
        ('Amount Details', {
            'fields': ('amount', 'currency')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmployeeLeave)
class EmployeeLeaveAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'status', 'created_at']
    list_filter = ['leave_type', 'status', 'start_date', 'employee__company', 'created_at']
    search_fields = ['employee__user__email', 'reason']
    readonly_fields = ['created_at']

    actions = ['approve_leaves', 'reject_leaves']

    def approve_leaves(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='approved', reviewed_at=timezone.now(), reviewed_by=request.user)
        self.message_user(request, f"Approved {queryset.count()} leave requests.")

    approve_leaves.short_description = "Approve selected leave requests"

    def reject_leaves(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='rejected', reviewed_at=timezone.now(), reviewed_by=request.user)
        self.message_user(request, f"Rejected {queryset.count()} leave requests.")

    reject_leaves.short_description = "Reject selected leave requests"

    fieldsets = (
        ('Leave Details', {
            'fields': ('employee', 'leave_type', 'start_date', 'end_date', 'reason')
        }),
        ('Status', {
            'fields': ('status', 'reviewed_by', 'reviewed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmployeeDeduction)
class EmployeeDeductionAdmin(admin.ModelAdmin):
    list_display = ['employee', 'deduction_type', 'amount', 'effective_month', 'end_month', 'created_at']
    list_filter = ['deduction_type', 'effective_month', 'employee__company', 'created_at']
    search_fields = ['employee__user__email', 'reason']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Deduction Details', {
            'fields': ('employee', 'deduction_type', 'amount', 'reason')
        }),
        ('Period', {
            'fields': ('effective_month', 'end_month')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )