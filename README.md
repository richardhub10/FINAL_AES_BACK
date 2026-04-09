# UA Clinic Appointment System (React Native + Django) with AES

This repo contains:
- **Backend**: Django + Django REST Framework + JWT auth
- **Mobile**: React Native (Expo)
- **AES feature**: Sensitive appointment fields (`reason`, `notes`) are **encrypted at rest** in SQLite using **AES-GCM** (AES-256 when using a 32-byte key).

## Backend (Django)

### 1) Create `.env`
Copy `.env.example` to `.env` and set `AES_MASTER_KEY_B64`.

PowerShell key generation (32 bytes → base64):

```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Maximum 256}))
```

Put the output into `.env`:

```env
AES_MASTER_KEY_B64=PASTE_BASE64_HERE
```

### 2) Install + migrate

```powershell
cd "c:\Users\Saigan\Documents\test-softwae dev\SecondSem_Robert(Richard)\AES"
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\python.exe backend\manage.py migrate
```

### 3) Run the server

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

API endpoints:
- `POST /api/auth/register/`
- `GET /api/auth/me/` (who am I / staff flag)
- `POST /api/auth/token/` (JWT login)
- `GET/POST /api/appointments/`

Staff behavior:
- Staff users can see **all** appointments and can set `status` to `confirmed`/`cancelled`.
- Patients can only edit their own `reason`/`notes`, and can only set `status` to `cancelled`.

Create a staff user (admin):

```powershell
.\.venv\Scripts\python.exe backend\manage.py createsuperuser
```

## Mobile (React Native / Expo)

```powershell
cd mobile
npm install
npm run android
```

In the app, set **API Base URL**:
- Android emulator: `http://10.0.2.2:8000`
- Web/iOS simulator: `http://localhost:8000`
- Physical phone: `http://<your-pc-lan-ip>:8000`

## AES implementation notes

- Encryption uses `cryptography`’s `AESGCM`.
- Encrypted DB format: `enc:v1:<nonce_b64>:<ciphertext_b64>`.
- The Django model field `EncryptedTextField` encrypts on save and decrypts when reading from DB.

## Tests

```powershell
.\.venv\Scripts\python.exe backend\manage.py test
```
