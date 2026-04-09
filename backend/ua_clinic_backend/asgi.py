"""
ASGI config for ua_clinic_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ua_clinic_backend.settings')

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
	# Ensure repo-root apps (like `clinic/`) are importable when running via ASGI.
	sys.path.insert(0, str(REPO_ROOT))

application = get_asgi_application()
