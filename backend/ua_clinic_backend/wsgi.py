"""
WSGI config for ua_clinic_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ua_clinic_backend.settings')

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
	# Ensure repo-root apps (like `clinic/`) are importable when running via WSGI.
	sys.path.insert(0, str(REPO_ROOT))

application = get_wsgi_application()
