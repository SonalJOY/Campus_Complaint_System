from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile & RBAC Role"
    fk_name = 'user'
    fields = ('role', 'phone', 'created_at')
    readonly_fields = ('created_at',)


class CustomUserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'get_phone', 'is_staff')
    list_filter = ('profile__role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'profile__phone')

    @admin.display(description='Role', ordering='profile__role')
    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else "-"

    @admin.display(description='Phone')
    def get_phone(self, obj):
        return obj.profile.phone if hasattr(obj, 'profile') else "-"


# Re-register User with customized Profile inline
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone')
    readonly_fields = ('created_at',)
