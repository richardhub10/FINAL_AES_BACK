"""DRF serializers for the clinic API.

Serializers define:
- Input validation rules (e.g., allowed appointment times, weekend restrictions)
- Output shape (what fields are returned to the frontend)
- Business rules enforced at the API boundary (e.g., staff hourly capacity)

Security note (AES-at-rest):
The `Appointment` model stores `reason` and `notes` encrypted in the database.
For defense-in-depth, this API *also* returns encrypted strings for `reason` and
`notes` by default. Plaintext is only returned via a dedicated decrypt endpoint
and only to authorized users.
"""

from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone
from zoneinfo import ZoneInfo
from rest_framework import serializers

from .crypto import encrypt_str
from .models import Appointment, UserProfile


class StaffUserSerializer(serializers.ModelSerializer):

    # These fields are read from the related UserProfile via `source="profile.<field>"`.
    birthday = serializers.DateField(source="profile.birthday", read_only=True)
    school_id = serializers.CharField(source="profile.school_id", read_only=True)
    contact_number = serializers.CharField(source="profile.contact_number", read_only=True)

    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_active",
            "date_joined",
            "birthday",
            "school_id",
            "contact_number",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "date_joined",
            "birthday",
            "school_id",
            "contact_number",
        ]


class RegisterSerializer(serializers.Serializer):
    """Validate and create a new user + profile.

    We use the email address as the username for a simple login experience.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    birthday = serializers.DateField()
    school_id = serializers.CharField(max_length=64)
    contact_number = serializers.CharField(max_length=32)

    def validate_email(self, value):
        # Normalize to a consistent form to avoid duplicate-account edge cases.
        User = get_user_model()
        email_norm = value.strip().lower()
        if User.objects.filter(email__iexact=email_norm).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email_norm

    def create(self, validated_data):
        User = get_user_model()

        password = validated_data.pop("password")
        birthday = validated_data.pop("birthday")
        school_id = validated_data.pop("school_id")
        contact_number = validated_data.pop("contact_number")

        email = validated_data.pop("email").strip().lower()

        # Use email as username for simple email+password login.
        user = User(
            username=email,
            email=email,
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        user.set_password(password)
        user.save()

        UserProfile.objects.create(
            user=user,
            birthday=birthday,
            school_id=school_id,
            contact_number=contact_number,
        )

        return user


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for Appointment CRUD.

    Important behaviors:
    - Adds patient-derived read-only fields (full name, age) for display.
    - Encrypts `reason` and `notes` in API output by default.
    - Enforces schedule constraints (weekdays only, hourly slots, UTC time).
    - Enforces staff hourly capacity when confirming.
    """

    patient_username = serializers.CharField(source="patient.username", read_only=True)
    patient_first_name = serializers.CharField(source="patient.first_name", read_only=True)
    patient_last_name = serializers.CharField(source="patient.last_name", read_only=True)
    patient_full_name = serializers.SerializerMethodField()
    patient_age = serializers.SerializerMethodField()
    doctor_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "patient_username",
            "patient_first_name",
            "patient_last_name",
            "patient_full_name",
            "patient_age",
            "doctor_name",
            "scheduled_for",
            "reason",
            "notes",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["patient", "created_at", "updated_at"]

    def get_patient_full_name(self, obj):  # noqa: ANN001
        first = (getattr(obj.patient, "first_name", "") or "").strip()
        last = (getattr(obj.patient, "last_name", "") or "").strip()
        full = (f"{first} {last}").strip()
        return full

    def get_patient_age(self, obj):  # noqa: ANN001
        profile = getattr(obj.patient, "profile", None)
        birthday = getattr(profile, "birthday", None)
        if not birthday:
            return None

        today = timezone.now().date()
        age = today.year - birthday.year - (
            (today.month, today.day) < (birthday.month, birthday.day)
        )
        return age if age >= 0 else None

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # By default, do NOT expose plaintext. Return AES-encrypted strings.
        # Decrypt endpoint can pass context {"return_plaintext": True}.
        if self.context.get("return_plaintext") is True:
            return data

        try:
            # Even though the DB stores ciphertext already, we re-encrypt for transport
            # so the frontend never accidentally displays plaintext unless the user
            # explicitly calls the decrypt endpoint.
            data["reason"] = encrypt_str(data.get("reason") or "")
            data["notes"] = encrypt_str(data.get("notes") or "")
        except Exception:  # noqa: BLE001
            # Fail closed: if encryption fails, don't leak plaintext.
            data["reason"] = ""
            data["notes"] = ""

        return data

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["patient"] = request.user
        if not validated_data.get("doctor_name"):
            validated_data["doctor_name"] = "General"
        return super().create(validated_data)

    def validate_scheduled_for(self, value):
        """Validate scheduling rules.

        Rules (PHT-based):
        - No weekend appointments
        - Exactly on the hour (minutes/seconds must be 0)
        - Allowed hours: 07:00 through 16:00 inclusive (clinic hours)
        """
        if not value:
            return value

        dt = value
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=timezone.utc)

        manila = ZoneInfo("Asia/Manila")
        dt_local = dt.astimezone(manila)

        if dt_local.weekday() in (5, 6):  # Sat/Sun
            raise serializers.ValidationError(
                "Appointments cannot be scheduled on Saturday or Sunday."
            )

        # Only allow 07:00 through 16:00 PHT (hourly).
        h = dt_local.hour
        m = dt_local.minute
        s = dt_local.second
        if s != 0 or m != 0:
            raise serializers.ValidationError(
                "Appointments must be scheduled on the hour between 07:00 and 16:00 PHT."
            )
        if h < 7 or h > 16:
            raise serializers.ValidationError(
                "Appointments must be scheduled between 07:00 and 16:00 PHT."
            )

        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            return attrs

        # Staff hourly capacity enforcement when confirming.
        # Max 5 confirmed appointments per hour (PHT).
        #
        # This is enforced here because this is the narrow point where status
        # changes to CONFIRMED.
        HOURLY_CAPACITY = 5
        instance = getattr(self, "instance", None)
        resulting_status = attrs.get("status") if "status" in attrs else getattr(instance, "status", None)
        resulting_scheduled_for = attrs.get("scheduled_for") if "scheduled_for" in attrs else getattr(instance, "scheduled_for", None)
        if request.user.is_staff and resulting_status == Appointment.Status.CONFIRMED and resulting_scheduled_for:
            dt = resulting_scheduled_for
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone=timezone.utc)
            manila = ZoneInfo("Asia/Manila")
            dt_local = dt.astimezone(manila)
            start_local = dt_local.replace(minute=0, second=0, microsecond=0)
            end_local = start_local + timedelta(hours=1)
            start = start_local.astimezone(timezone.utc)
            end = end_local.astimezone(timezone.utc)
            qs = Appointment.objects.filter(
                status=Appointment.Status.CONFIRMED,
                scheduled_for__gte=start,
                scheduled_for__lt=end,
            )
            if instance is not None and getattr(instance, "pk", None):
                qs = qs.exclude(pk=instance.pk)
            if qs.count() >= HOURLY_CAPACITY:
                raise serializers.ValidationError(
                    {
                        "status": "This time slot is full. Maximum 5 confirmed appointments per hour."
                    }
                )

        # Staff can accept/confirm/cancel, but must not create appointments.
        if request.method == "POST" and request.user.is_staff:
            raise serializers.ValidationError(
                {"detail": "Staff accounts cannot create appointments."}
            )

        # For updates: restrict what non-staff users can change.
        if request.method in ("PUT", "PATCH") and not request.user.is_staff:
            allowed = {"reason", "notes", "status"}
            disallowed = set(attrs.keys()) - allowed
            if disallowed:
                raise serializers.ValidationError(
                    {"detail": f"Patients cannot update fields: {sorted(disallowed)}"}
                )

            if "status" in attrs and attrs["status"] != Appointment.Status.CANCELLED:
                raise serializers.ValidationError(
                    {"status": "Patients may only set status to 'cancelled'."}
                )

        return attrs
