"""Django admin configuration.

Used mainly for:
- Viewing/updating appointments in an admin UI
- Viewing accounts and their profiles
- Enabling/disabling accounts via bulk actions (presentation/admin convenience)
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Appointment, UserProfile

# Use a custom admin homepage to provide quick navigation.
admin.site.index_template = "admin/custom_index.html"


@admin.action(description="Deactivate selected user accounts")
def deactivate_users(_modeladmin, _request, queryset):  # noqa: ANN001
	queryset.update(is_active=False)


@admin.action(description="Reactivate selected user accounts")
def reactivate_users(_modeladmin, _request, queryset):  # noqa: ANN001
	queryset.update(is_active=True)


class UserProfileInline(admin.StackedInline):
	model = UserProfile
	can_delete = False
	extra = 0
	fk_name = "user"


User = get_user_model()

try:
	# Unregister the default Django User admin so we can register our customized version.
	admin.site.unregister(User)
except admin.sites.NotRegistered:
	pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
	inlines = [UserProfileInline]
	actions = [deactivate_users, reactivate_users]

	list_display = (
		"username",
		"email",
		"first_name",
		"last_name",
		"is_staff",
		"is_active",
		"date_joined",
	)
	list_filter = ("is_staff", "is_superuser", "is_active")
	search_fields = (
		"username",
		"email",
		"first_name",
		"last_name",
		"profile__school_id",
		"profile__contact_number",
	)
	ordering = ("username",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "school_id", "contact_number", "birthday", "updated_at")
	search_fields = ("user__username", "user__email", "school_id", "contact_number")
	list_select_related = ("user",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
	list_display = ("id", "patient", "doctor_name", "scheduled_for", "status", "created_at")
	list_filter = ("status", "scheduled_for")
	search_fields = ("doctor_name", "patient__username", "patient__email")
	list_select_related = ("patient",)
	date_hierarchy = "scheduled_for"
