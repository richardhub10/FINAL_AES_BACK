"""Backend test suite.

These tests support the presentation by proving:
- AES encryption at rest: sensitive fields are not stored as plaintext in DB
- Permissions rules: what patients can/can't do vs staff
"""

import base64
import datetime

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from rest_framework.test import APIClient

from .models import Appointment

@override_settings(AES_MASTER_KEY_B64=base64.b64encode(b"0" * 32).decode("ascii"))
class EncryptionAtRestTests(TestCase):
	def test_encrypted_fields_are_not_plaintext_in_db(self):
		# Create an appointment with sensitive fields.
		user = User.objects.create_user(username="alice", password="pass1234")

		appt = Appointment.objects.create(
			patient=user,
			doctor_name="Dr. Bob",
			scheduled_for=timezone.make_aware(datetime.datetime(2030, 1, 1, 10, 0, 0)),
			reason="Sensitive reason",
			notes="Sensitive notes",
		)

		# ORM instance should expose plaintext
		self.assertEqual(appt.reason, "Sensitive reason")
		self.assertEqual(appt.notes, "Sensitive notes")

		# Raw DB should not contain plaintext (use SQL cursor to bypass field decryption)
		with connection.cursor() as cursor:
			cursor.execute(
				"SELECT reason, notes FROM clinic_appointment WHERE id = %s",
				[appt.id],
			)
			reason_raw, notes_raw = cursor.fetchone()

		self.assertNotEqual(reason_raw, "Sensitive reason")
		self.assertTrue(str(reason_raw).startswith("enc:v1:"))
		self.assertNotEqual(notes_raw, "Sensitive notes")
		self.assertTrue(str(notes_raw).startswith("enc:v1:"))

		# Re-fetch should decrypt
		appt2 = Appointment.objects.get(id=appt.id)
		self.assertEqual(appt2.reason, "Sensitive reason")
		self.assertEqual(appt2.notes, "Sensitive notes")


@override_settings(AES_MASTER_KEY_B64=base64.b64encode(b"0" * 32).decode("ascii"))
class AppointmentPermissionsTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.patient = User.objects.create_user(username="patient", password="pass1234")
		self.staff = User.objects.create_user(username="staff", password="pass1234", is_staff=True)
		self.appt = Appointment.objects.create(
			patient=self.patient,
			doctor_name="Dr. Who",
			scheduled_for=timezone.make_aware(datetime.datetime(2030, 1, 1, 10, 0, 0)),
			reason="r",
			notes="n",
		)

	def test_patient_cannot_confirm(self):
		self.client.force_authenticate(user=self.patient)
		res = self.client.patch(f"/api/appointments/{self.appt.id}/", {"status": "confirmed"}, format="json")
		self.assertEqual(res.status_code, 400)

	def test_patient_can_cancel(self):
		self.client.force_authenticate(user=self.patient)
		res = self.client.patch(f"/api/appointments/{self.appt.id}/", {"status": "cancelled"}, format="json")
		self.assertEqual(res.status_code, 200)

	def test_patient_cannot_change_doctor_or_time(self):
		self.client.force_authenticate(user=self.patient)
		res = self.client.patch(
			f"/api/appointments/{self.appt.id}/",
			{"doctor_name": "Dr. Evil"},
			format="json",
		)
		self.assertEqual(res.status_code, 400)

	def test_staff_can_confirm(self):
		self.client.force_authenticate(user=self.staff)
		res = self.client.patch(f"/api/appointments/{self.appt.id}/", {"status": "confirmed"}, format="json")
		self.assertEqual(res.status_code, 200)
