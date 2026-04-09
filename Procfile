web: python manage.py migrate --noinput && python manage.py ensure_default_admin && gunicorn ua_clinic_backend.wsgi:application --chdir backend --bind 0.0.0.0:$PORT
