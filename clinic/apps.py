"""App configuration for the `clinic` Django app.

This hooks into Django startup to optionally "bootstrap" a default admin user.

Why:
- On platforms like Render, you may want an initial admin for setup/testing.
- The bootstrap is controlled by environment variables, so secrets are not
    hard-coded in the repository.

Environment variables used:
- DEFAULT_ADMIN_USERNAME / DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSWORD
- DEFAULT_ADMIN_FORCE_RESET
- DEFAULT_ADMIN_BOOTSTRAP_ON_STARTUP
"""

import os

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate
from django.db.utils import OperationalError, ProgrammingError


class ClinicConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clinic'

    def ready(self):  # noqa: D401
        """Create default admin user if configured via environment variables."""

        def ensure_default_admin(sender, **kwargs):  # noqa: ANN001
            # This function runs after migrations (`post_migrate`).
            # It can also run once at startup (see below) to be more robust on
            # some PaaS environments.
            try:
                username = os.environ.get("DEFAULT_ADMIN_USERNAME", "Admin").strip() or "Admin"
                password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "").strip()
                email = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@example.com").strip()
                force_reset = (
                    os.environ.get("DEFAULT_ADMIN_FORCE_RESET", "false").lower() == "true"
                )

                # If password isn't provided, do nothing (safer than hardcoding a secret).
                if not password:
                    if settings.DEBUG:
                        print(
                            "[ua-clinic] DEFAULT_ADMIN_PASSWORD not set; skipping default admin creation."
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

                # Ensure privileges are correct
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

                # Set password when creating, forcing reset, or when user has no usable password.
                if created or force_reset or not user.has_usable_password():
                    user.set_password(password)
                    changed = True

                if changed:
                    user.save()
                    if created:
                        print(f"[ua-clinic] Created default admin user: {username}")
                    else:
                        msg = "Updated default admin"
                        if force_reset or not user.has_usable_password():
                            msg += " (password set/reset)"
                        print(f"[ua-clinic] {msg}: {username}")
            except (OperationalError, ProgrammingError) as e:
                # DB might not be ready during early startup or migration phases.
                if settings.DEBUG:
                    print(f"[ua-clinic] Admin bootstrap skipped (db not ready): {e}")

        post_migrate.connect(ensure_default_admin, sender=self)

        # Also try on server startup (Render can skip/override build steps).
        bootstrap_on_startup = (
            os.environ.get("DEFAULT_ADMIN_BOOTSTRAP_ON_STARTUP", "true").lower() != "false"
        )
        if bootstrap_on_startup:
            ensure_default_admin(sender=self)
