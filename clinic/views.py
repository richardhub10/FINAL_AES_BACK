"""API views for the clinic app.

This module exposes the endpoints consumed by the Expo frontend:
- Registration (`/api/auth/register/`)
- Current user (`/api/auth/me/`)
- Appointments CRUD (`/api/appointments/...`)
- Staff account management (`/api/staff/users/...`)

Security note (AES):
Appointments contain sensitive fields (reason/notes). Those fields are:
- Encrypted at rest in the DB (EncryptedTextField)
- Returned encrypted by default via the serializer
- Returned plaintext ONLY via the `decrypt` action and only to owner/staff
"""

from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone

from .models import Appointment
from .serializers import AppointmentSerializer, RegisterSerializer, StaffUserSerializer


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register(request):
	"""Create a new user account.

	The serializer also creates the associated `UserProfile`.
	"""
	serializer = RegisterSerializer(data=request.data)
	serializer.is_valid(raise_exception=True)
	user = serializer.save()
	return Response({"id": user.id, "email": user.email, "username": user.username})


@api_view(["GET"])
def me(request):
	"""Return the currently authenticated user's info (used to detect staff)."""
	user = request.user
	profile = getattr(user, "profile", None)
	return Response(
		{
			"id": user.id,
			"username": user.username,
			"email": user.email,
			"first_name": user.first_name,
			"last_name": user.last_name,
			"birthday": getattr(profile, "birthday", None),
			"school_id": getattr(profile, "school_id", ""),
			"contact_number": getattr(profile, "contact_number", ""),
			"is_staff": user.is_staff,
		}
	)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def availability(request):
	"""Return global confirmed-slot counts for a date range.

	Purpose:
	- Students only have permission to list *their own* appointments.
	- Availability, however, must reflect *all* confirmed appointments so a new
	  student sees accurate used/total per time slot.

	This endpoint returns only aggregated counts (no patient details).

	Query params:
	- start: YYYY-MM-DD (inclusive)
	- end:   YYYY-MM-DD (inclusive)

	Response:
	{
	  "confirmed_by_date": {"2026-04-11": 3, ...},
	  "confirmed_by_slot": {"2026-04-11 07:00": 2, ...}
	}
	"""
	start_ymd = (request.query_params.get("start") or "").strip()
	end_ymd = (request.query_params.get("end") or "").strip()

	if not start_ymd or not end_ymd:
		return Response({"detail": "Query params 'start' and 'end' are required (YYYY-MM-DD)."}, status=400)

	try:
		start_date = datetime.strptime(start_ymd, "%Y-%m-%d").date()
		end_date = datetime.strptime(end_ymd, "%Y-%m-%d").date()
	except ValueError:
		return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

	if end_date < start_date:
		return Response({"detail": "'end' must be on or after 'start'."}, status=400)

	# Interpret start/end as Philippines dates and convert to UTC boundaries.
	manila = ZoneInfo("Asia/Manila")
	start_local = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), timezone=manila)
	end_local_exclusive = timezone.make_aware(
		datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
		timezone=manila,
	)
	start_dt = start_local.astimezone(timezone.utc)
	end_dt_exclusive = end_local_exclusive.astimezone(timezone.utc)

	qs = Appointment.objects.filter(
		status=Appointment.Status.CONFIRMED,
		scheduled_for__gte=start_dt,
		scheduled_for__lt=end_dt_exclusive,
	).only("scheduled_for")

	confirmed_by_date = {}
	confirmed_by_slot = {}
	for scheduled_for in qs.values_list("scheduled_for", flat=True):
		if not scheduled_for:
			continue
		dt_val = scheduled_for
		if timezone.is_naive(dt_val):
			dt_val = timezone.make_aware(dt_val, timezone=timezone.utc)
		dt_local = dt_val.astimezone(manila)
		ymd = dt_local.strftime("%Y-%m-%d")
		hhmm = dt_local.strftime("%H:%M")
		slot_key = f"{ymd} {hhmm}"
		confirmed_by_date[ymd] = int(confirmed_by_date.get(ymd, 0)) + 1
		confirmed_by_slot[slot_key] = int(confirmed_by_slot.get(slot_key, 0)) + 1

	return Response({"confirmed_by_date": confirmed_by_date, "confirmed_by_slot": confirmed_by_slot})


class IsOwnerOrStaff(permissions.BasePermission):
	"""Object-level permission: appointment owner OR staff can access."""

	def has_object_permission(self, request, view, obj):  # noqa: ANN001
		return request.user and (request.user.is_staff or obj.patient_id == request.user.id)


class AppointmentViewSet(viewsets.ModelViewSet):
	serializer_class = AppointmentSerializer
	permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]

	def get_queryset(self):
		# Staff can see all appointments; patients can only see their own.
		user = self.request.user
		if user.is_staff:
			return Appointment.objects.select_related("patient", "patient__profile").all()
		return Appointment.objects.select_related("patient", "patient__profile").filter(patient=user)

	@action(detail=True, methods=["GET"], url_path="decrypt")
	def decrypt(self, request, pk=None):  # noqa: ANN001
		"""Return plaintext reason/notes for one appointment.

		Why this exists:
		- The normal list/detail endpoints return AES-encrypted strings for privacy.
		- For UX (reading details / generating ticket), authorized users can request
		  plaintext explicitly.
		"""
		appt = self.get_object()  # enforces IsOwnerOrStaff
		serializer = self.get_serializer(appt, context={"request": request, "return_plaintext": True})
		return Response(serializer.data)


class IsStaffUser(permissions.BasePermission):
	"""Permission: only authenticated staff accounts."""

	def has_permission(self, request, view):  # noqa: ANN001
		return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class StaffUserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
	"""Staff-only view of registered accounts.

	Supports:
	- GET /api/staff/users/
	- PATCH /api/staff/users/{id}/  (is_active only)
	"""

	serializer_class = StaffUserSerializer
	permission_classes = [permissions.IsAuthenticated, IsStaffUser]

	def get_queryset(self):
		User = get_user_model()
		return User.objects.select_related("profile").all().order_by("-date_joined")

	def partial_update(self, request, *args, **kwargs):  # noqa: ANN001
		# Only allow toggling is_active.
		allowed = {"is_active"}
		extra = set(request.data.keys()) - allowed
		if extra:
			return Response({"detail": "Only 'is_active' can be updated."}, status=400)

		# Prevent staff from deactivating themselves by mistake.
		obj = self.get_object()
		if obj.pk == request.user.pk and request.data.get("is_active") is False:
			return Response({"detail": "You cannot deactivate your own account."}, status=400)

		return super().partial_update(request, *args, **kwargs)
