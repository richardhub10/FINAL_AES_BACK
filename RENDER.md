# Deploying the Backend to Render

Create a **Web Service** on Render from this repo.

Suggested settings:
- Environment: `Python 3`
- Build command: `pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py ensure_default_admin`
- Start command: `gunicorn ua_clinic_backend.wsgi:application --chdir backend --bind 0.0.0.0:$PORT`

Environment variables (Render dashboard):
- `DJANGO_SECRET_KEY`: required
- `DJANGO_DEBUG`: set to `false` for production
- `DJANGO_ALLOWED_HOSTS`: e.g. `*` (or your Render domain)
- `CORS_ALLOW_ALL_ORIGINS`: `true` for quick testing (tighten later)
- `AES_MASTER_KEY_B64`: required (base64 32-byte key)

Persistent accounts (IMPORTANT):
- If you use the default SQLite database, Render will wipe it on restarts/redeploys.

Option A (recommended): Postgres
- Create a **Render Postgres** database and attach it to this web service so Render provides `DATABASE_URL`.
- With `DATABASE_URL` set, Django will use Postgres and user accounts will persist across restarts.

Supabase Postgres (instead of Render Postgres)
- Set `DATABASE_URL` to your Supabase connection string, for example:
	- `postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require`

If you see this error during `migrate` on Render:
- `OperationalError: ... (IPv6 ...) port 5432 failed: Network is unreachable`

Fix option 1 (recommended): use Supabase pooler
- In Supabase dashboard: **Project Settings → Database → Connection string → Connection pooling**.
- Use the **Transaction pooler** connection string as `DATABASE_URL` (it typically avoids IPv6-only resolution).

Fix option 2: force IPv4 via `DATABASE_HOSTADDR`
- Run locally:
	- `nslookup db.<project-ref>.supabase.co`
- Copy one IPv4 address from the output (an `Address:` that looks like `123.45.67.89`).
- Add a Render env var:
	- `DATABASE_HOSTADDR=123.45.67.89`
- Redeploy. The backend will keep the hostname for TLS but connect using IPv4.

Option B (no Postgres): Persistent Disk + SQLite
- Create a **Persistent Disk** on the backend service and mount it at `/var/data`.
- Add env var `SQLITE_PATH=/var/data/db.sqlite3`.
- Redeploy. The SQLite file will be stored on the disk and will persist across restarts.

Notes:
- Render automatically provides `RENDER_EXTERNAL_HOSTNAME` (like `aes-back.onrender.com`). The backend auto-adds this to `ALLOWED_HOSTS` to prevent `Bad Request (400)` due to `DisallowedHost`.

Default admin bootstrap (created automatically during `migrate`):
- `DEFAULT_ADMIN_USERNAME`: default `Admin`
- `DEFAULT_ADMIN_PASSWORD`: required if you want the admin auto-created
- `DEFAULT_ADMIN_EMAIL`: default `admin@example.com`
- `DEFAULT_ADMIN_FORCE_RESET`: set to `true` for ONE redeploy to force-reset the admin password (optional)

Admin login fix on Render:
- Set `DEFAULT_ADMIN_USERNAME=Admin`
- Set `DEFAULT_ADMIN_PASSWORD=Admin123`
- Set `DEFAULT_ADMIN_FORCE_RESET=true`
- Redeploy (so the build/start commands run and the admin bootstrap runs)
- After you confirm you can log in, you can set `DEFAULT_ADMIN_FORCE_RESET=false`

Notes:
- Django usernames are case-sensitive when logging in. If your username is `Admin`, you must log in using exactly `Admin` (not `admin`).

Important:
- If you rotate `AES_MASTER_KEY_B64`, previously encrypted data cannot be decrypted.
