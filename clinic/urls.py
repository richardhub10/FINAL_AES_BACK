"""URL routes for the `clinic` Django app.

Mounted under `/api/` by the project-level urls.

We use DRF routers for ViewSets:
- `/api/appointments/` (AppointmentViewSet)
- `/api/staff/users/` (StaffUserViewSet)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppointmentViewSet, StaffUserViewSet, availability, me, register

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet, basename="appointment")
router.register(r"staff/users", StaffUserViewSet, basename="staff-user")

urlpatterns = [
    path("auth/register/", register, name="register"),
    path("auth/me/", me, name="me"),
    path("availability/", availability, name="availability"),
    path("", include(router.urls)),
]
