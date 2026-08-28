from django.contrib import admin
from django.db.models import Count
from .models import Category, Complaint, ComplaintHistory


class ComplaintHistoryInline(admin.TabularInline):
    model = ComplaintHistory
    extra = 0
    can_delete = False
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'remarks', 'changed_at')
    ordering = ('-changed_at',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'complaints_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(total_complaints=Count('complaints'))

    @admin.display(description='Total Complaints', ordering='total_complaints')
    def complaints_count(self, obj):
        return obj.total_complaints


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        'complaint_id',
        'title',
        'category',
        'priority',
        'status',
        'submitted_by',
        'assigned_to',
        'created_at'
    )
    list_filter = ('status', 'priority', 'category', 'created_at')
    search_fields = (
        'complaint_id',
        'title',
        'description',
        'location',
        'submitted_by__username',
        'assigned_to__username'
    )
    readonly_fields = ('complaint_id', 'status', 'created_at', 'updated_at', 'resolved_at', 'closed_at')
    inlines = [ComplaintHistoryInline]
    
    fieldsets = (
        ('Identification & Status', {
            'fields': ('complaint_id', 'status', 'priority', 'category')
        }),
        ('Complaint Details', {
            'fields': ('title', 'description', 'location', 'image')
        }),
        ('Parties Involved', {
            'fields': ('submitted_by', 'assigned_to')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ComplaintHistory)
class ComplaintHistoryAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('old_status', 'new_status', 'changed_at')
    search_fields = (
        'complaint__complaint_id',
        'complaint__title',
        'changed_by__username',
        'remarks'
    )
    readonly_fields = ('complaint', 'old_status', 'new_status', 'changed_by', 'remarks', 'changed_at')
