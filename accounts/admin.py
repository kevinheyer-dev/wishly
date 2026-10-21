from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import BirthdayReminder, FamilyGroup, Membership, Profile, User


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(User)
class WishlyUserAdmin(UserAdmin):
    inlines = [MembershipInline]


@admin.register(FamilyGroup)
class FamilyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [MembershipInline]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "family_group", "birth_day", "birth_month")
    list_filter = ("family_group",)
    search_fields = ("name", "user__username", "user__first_name", "user__last_name")
    filter_horizontal = ("guardians",)


@admin.register(BirthdayReminder)
class BirthdayReminderAdmin(admin.ModelAdmin):
    list_display = ("profile", "birthday", "sent_at")
