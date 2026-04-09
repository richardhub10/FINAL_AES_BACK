"""Database models for the clinic application.

Highlights for the presentation:
- `EncryptedTextField` transparently encrypts/decrypts sensitive text fields.
- `Appointment` stores the appointment schedule + encrypted `reason`/`notes`.
- `UserProfile` stores additional student metadata linked to Django's User.
"""

from django.conf import settings
from django.db import models

from .crypto import decrypt_str, encrypt_str


class EncryptedTextField(models.TextField):
	"""Django model field that transparently encrypts/decrypts text.

	How it works:
	- When Django reads a row from the DB, `from_db_value` and `to_python` run and
	  we decrypt the stored ciphertext into plaintext.
	- When Django writes to the DB, `get_prep_value` runs and we encrypt the
	  plaintext into a versioned payload string.

	This keeps the rest of the application working with *plaintext* strings while
	the database only stores ciphertext.
	"""

	def from_db_value(self, value, expression, connection):  # noqa: ANN001
		"""Convert the DB value (ciphertext) into Python (plaintext)."""
		if value is None:
			return value
		return decrypt_str(value)

	def to_python(self, value):  # noqa: ANN001
		"""Ensure values assigned in Python are normalized to plaintext strings."""
		if value is None:
			return value
		if isinstance(value, str):
			return decrypt_str(value)
		return value

	def get_prep_value(self, value):  # noqa: ANN001
		"""Convert Python plaintext into a DB-storable encrypted payload string."""
		value = super().get_prep_value(value)
		if value is None:
			return value
		return encrypt_str(value)


class Appointment(models.Model):
	"""An appointment request created by a student/patient.

	Business rules are enforced primarily in serializers:
	- Patients can create/cancel their own appointments
	- Staff can confirm/cancel and are subject to hourly capacity
	"""

	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		CONFIRMED = "confirmed", "Confirmed"
		CANCELLED = "cancelled", "Cancelled"

	patient = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="appointments",
	)
	doctor_name = models.CharField(max_length=120)
	scheduled_for = models.DateTimeField()
	reason = EncryptedTextField(blank=True, default="")
	notes = EncryptedTextField(blank=True, default="")
	status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-scheduled_for"]

	def __str__(self) -> str:
		return f"Appointment({self.patient_id}, {self.doctor_name}, {self.scheduled_for})"


class UserProfile(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="profile",
	)
	birthday = models.DateField(null=True, blank=True)
	school_id = models.CharField(max_length=64, blank=True, default="")
	contact_number = models.CharField(max_length=32, blank=True, default="")

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:
		return f"UserProfile({self.user_id})"
