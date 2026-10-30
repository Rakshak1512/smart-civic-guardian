# Smart Civic Guardian

Smart Civic Guardian is a full-stack civic engagement and issue tracking platform connecting citizens with municipal authorities and urban administrators. Built with Python Flask, HTML5/CSS3/JavaScript, Supabase PostgreSQL, and Supabase Storage.

---

## Key Features

- **Civic Issue Reporting**: Citizen reporting with category selection (Garbage, Water Leakage, Electricity Issue, Pothole), AI category & priority heuristics, duplicate detection, and image uploads.
- **Dedicated Port Separation & Vercel Unified Deployment**: Runs locally as separated services (`http://localhost:3000` for frontend, `http://localhost:5000` for backend REST API) and deploys smoothly to Vercel as a full-stack serverless app (`vercel.json` + `api/index.py`).
- **Cryptographic OTP Authentication**:
  - 6-digit cryptographically generated OTP codes using Python `secrets`.
  - Stored strictly as **keyed HMAC-SHA256 digests with server-side `OTP_PEPPER`** in the Supabase PostgreSQL `email_otps` table.
  - Plaintext OTPs are **never stored** in the database or written to logs.
  - Purpose isolation (`registration` vs `password_reset`), unique challenge IDs, constant-time `hmac.compare_digest` verification, 5-minute expiry, and 5-attempt brute-force protection.
  - Dispatch via Gmail SMTP TLS with responsive HTML templates.
- **Simplified 6-Character Password Policy**: 6-character/digit minimum password for account creation and password recovery.
- **Top Navigation & Back Buttons**:
  - `/` and `/home` both serve the complete homepage.
  - Professional **`← Back`** button on the Login page with smart history tracking and homepage fallback.
  - Back buttons on Register, Forgot Password, and OTP verification cards.
- **Supabase PostgreSQL & Cloud Storage**:
  - 8 production tables: `users`, `authorities`, `complaints`, `notifications`, `feedback`, `password_resets`, `contact_messages`, and `email_otps`.
  - Private Supabase Storage bucket `images` for complaint and resolution photo uploads.

---

## Project Structure

```
smart-civic-guardian/
├── api/
│   └── index.py               # Vercel serverless WSGI entry point
├── backend/
│   ├── app/
│   │   ├── models/            # PostgreSQL models (user, issue, authority, etc.)
│   │   ├── routes/            # Flask blueprints (auth, issue, admin, api, analytics)
│   │   ├── services/          # Services (otp_service, storage_service, etc.)
│   │   ├── config.py          # App configuration
│   │   └── db.py              # Supabase PostgreSQL database adapter
│   ├── .env.example           # Environment template without secrets
│   └── run.py                 # Backend API runner (port 5000)
├── frontend/
│   ├── static/                # CSS, JS, images, icons
│   ├── templates/             # Jinja2 HTML templates
│   │   ├── auth/              # login, register, forgot_password, verify_otp, reset_password
│   │   ├── citizen/           # report_issue, my_complaints, track_status, civic_map
│   │   ├── admin/             # dashboard, complaints, analytics, users, map
│   │   └── shared/            # navbar, footer, error
│   ├── server.py              # Dedicated frontend web server (port 3000)
│   └── run.py                 # Frontend runner
├── database/
│   ├── supabase_schema.sql    # Full PostgreSQL schema with email_otps table
│   └── migrate_to_supabase.py # SQLite to Supabase migration script
├── push_to_github.bat         # Automated one-click GitHub push helper
├── vercel.json                # Vercel serverless configuration
├── requirements.txt           # Python dependencies
└── README.md
```

---

## Environment Configuration

Configure your environment variables in `backend/.env` (and Vercel Project Settings for production):

```env
FLASK_ENV=development
FLASK_DEBUG=0
SECRET_KEY=your-secure-random-secret-key-32-chars

# Server & Port Configuration
PORT=5000
HOST=127.0.0.1
BACKEND_URL=http://localhost:5000
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Cryptographic OTP Pepper (Server-side HMAC secret)
OTP_PEPPER=your-server-side-cryptographic-pepper-hex-string

# SMTP Email Configuration (Gmail TLS)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# Supabase PostgreSQL & Storage Configuration
SUPABASE_URL=https://[PROJECT-REF].supabase.co
SUPABASE_SERVICE_ROLE_KEY=[YOUR-SERVICE-ROLE-KEY]
SUPABASE_BUCKET=images
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
```

---

## Running Locally

### 1. Start Backend REST API (Port 5000)
```powershell
python backend/run.py
```
* API Health: `http://localhost:5000/api/health`
* API Root: `http://localhost:5000/`

### 2. Start Frontend Web Service (Port 3000)
```powershell
python frontend/run.py
```
* Website: `http://localhost:3000` or `http://localhost:3000/home`

---

## Deploying on Vercel

1. Push your repository to GitHub.
2. In [Vercel Dashboard](https://vercel.com), click **Add New Project** and select `smart-civic-guardian`.
3. In **Environment Variables**, add:
   - `DATABASE_URL`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_BUCKET=images`
   - `OTP_PEPPER`
   - `SECRET_KEY`
   - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`
4. Click **Deploy**. Vercel will automatically build using `api/index.py` and serve static assets via `/frontend/static`.

---

## Demo Accounts

The login page contains a 1-click **Use Account** and **Copy Credentials** panel with pre-seeded demo accounts:

| Role | Email | Password | Access / Permissions |
|---|---|---|---|
| **Citizen** | `citizen@example.com` | `Citizen@123` | Report issues, track status, view notifications, submit feedback |
| **Authority** | `admin@example.com` | `Admin@123` | Department complaints, update issue status, upload resolved photos |
| **Administrator** | `superadmin@example.com` | `Admin@123` | Full admin panel, all complaints, analytics, manage authorities |

---

## Security Highlights

1. **HMAC-SHA256 Peppered OTPs**: Stored in PostgreSQL `email_otps` table with server-side pepper `OTP_PEPPER`, purpose separation, and constant-time comparison `hmac.compare_digest`.
2. **Brute-Force & Replay Protection**: Max 5 attempts enforced atomically in PostgreSQL, 5-minute strict expiration, 60-second resend cooldown, and single-use challenge consumption (`consumed_at`).
3. **No Credential Exposure**: `.env` and database files are strictly excluded via `.gitignore`.
