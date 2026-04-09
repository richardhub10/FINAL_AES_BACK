#!/usr/bin/env python
"""Root manage.py shim for Render and local convenience.

Render commonly runs `python manage.py ...` from the repo root.
Our real Django project lives in the `backend/` folder.

This shim adds `backend/` to PYTHONPATH and delegates to Django.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    backend_dir = repo_root / "backend"

    # Ensure backend package (ua_clinic_backend) is importable
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    # Ensure root-level apps like `clinic` are importable
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ua_clinic_backend.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
