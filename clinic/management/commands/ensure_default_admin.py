"""Management command: ensure a default admin exists.

This is useful for deployments (e.g., Render) where you want an initial admin
user to exist without manually running `createsuperuser`.

The command reads env vars (see help text) and then:
- Creates the user if it doesn't exist
- Ensures is_staff/is_superuser/is_active flags are correct
- Optionally sets/resets the password
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create/update a default admin user from environment variables."

    def handle(self, *args, **options):  # noqa: ANN002, ANN003
        username = os.environ.get("DEFAULT_ADMIN_USERNAME", "Admin").strip() or "Admin"
        password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "").strip()
        email = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@example.com").strip()
        force_reset = os.environ.get("DEFAULT_ADMIN_FORCE_RESET", "false").lower() == "true"

        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "[ua-clinic] DEFAULT_ADMIN_PASSWORD not set; skipping default admin creation."
                )
            )
            return

        User = get_user_model()

        user = User.objects.filter(username__iexact=username).first()
        if not user and email:
            user = User.objects.filter(email__iexact=email).first()
        created = False
        if not user:
            user = User(
                username=username,
                email=email,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            created = True

        changed = created

        if not getattr(user, "is_active", True):
            user.is_active = True
            changed = True
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if hasattr(user, "email") and email and getattr(user, "email", "") != email:
            user.email = email
            changed = True

        if created or force_reset or not user.has_usable_password():
            user.set_password(password)
            changed = True

        if changed:
            user.save()
            if created:
                self.stdout.write(self.style.SUCCESS(f"[ua-clinic] Created default admin user: {username}"))
            else:
                msg = "[ua-clinic] Updated default admin"
                if force_reset or not user.has_usable_password():
                    msg += " (password set/reset)"
                msg += f": {username}"
                self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stdout.write(self.style.SUCCESS(f"[ua-clinic] Default admin already up-to-date: {username}"))
