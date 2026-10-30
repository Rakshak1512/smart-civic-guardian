"""
OTP Service for Smart Civic Guardian.
Handles 6-digit cryptographically secure OTP generation, HMAC-SHA256 peppered hashing,
database storage in PostgreSQL `email_otps` table, expiry timing (5 minutes),
attempt limits, resend cooldowns, and SMTP dispatch via Gmail TLS.
"""

import hashlib
import hmac
import os
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

OTP_EXPIRY_MINUTES = 5
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def get_otp_pepper() -> bytes:
    """Returns the cryptographic pepper byte string from environment or config."""
    pepper = os.environ.get("OTP_PEPPER")
    if not pepper:
        try:
            from flask import current_app
            if current_app:
                pepper = current_app.config.get("OTP_PEPPER")
        except Exception:
            pass
    if not pepper:
        pepper = os.environ.get("SECRET_KEY", "smart-civic-guardian-secure-otp-pepper-2026")
    return str(pepper).encode("utf-8")


def generate_otp() -> str:
    """Generates a cryptographically secure 6-digit OTP string."""
    return f"{secrets.randbelow(900000) + 100000}"


def hash_otp_hmac(otp_code: str, challenge_id: str = "", purpose: str = "") -> str:
    """
    Computes a keyed HMAC-SHA256 digest using server-side OTP_PEPPER,
    unique challenge_id, and specific purpose to protect against brute-force attacks.
    """
    pepper = get_otp_pepper()
    payload = f"{str(otp_code).strip()}:{str(challenge_id).strip()}:{str(purpose).strip()}".encode("utf-8")
    return hmac.new(pepper, payload, hashlib.sha256).hexdigest()


def hash_otp(otp_string: str, salt: str = "") -> str:
    """Legacy helper for backward compatibility; calls hash_otp_hmac."""
    return hash_otp_hmac(otp_string, challenge_id=salt, purpose="")


def _get_pg_connection():
    """Returns a direct psycopg2 connection to Supabase PostgreSQL."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        try:
            from flask import current_app
            if current_app:
                db_url = current_app.config.get("DATABASE_URL")
        except Exception:
            pass
    if not db_url:
        return None
    try:
        import psycopg2
        return psycopg2.connect(db_url)
    except Exception:
        return None


def store_otp_challenge(user_email: str, otp_code: str, purpose: str) -> tuple[bool, str, str | None]:
    """
    Creates and stores a new OTP challenge in PostgreSQL `email_otps` table.
    Invalidates any previous active challenges for the same (email, purpose).
    Returns (True, challenge_id, None) on success or (False, "", error_msg) on failure.
    """
    challenge_id = str(uuid.uuid4())
    otp_hash = hash_otp_hmac(otp_code, challenge_id=challenge_id, purpose=purpose)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    email_clean = user_email.strip().lower()

    conn = _get_pg_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Invalidate prior active OTPs for this email and purpose
            cur.execute(
                "UPDATE email_otps SET is_used = TRUE WHERE LOWER(user_email) = %s AND purpose = %s AND is_used = FALSE;",
                (email_clean, purpose)
            )
            # Insert the new peppered digest
            cur.execute(
                """
                INSERT INTO email_otps (user_email, otp_hash, purpose, challenge_id, expires_at, attempts, max_attempts, is_used)
                VALUES (%s, %s, %s, %s, %s, 0, %s, FALSE);
                """,
                (email_clean, otp_hash, purpose, challenge_id, expires_at, MAX_ATTEMPTS)
            )
            conn.commit()
            cur.close()
            conn.close()
            return True, challenge_id, None
        except Exception as exc:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
            return False, "", str(exc)

    # Fallback to Supabase Python client if direct PostgreSQL connection is unavailable
    try:
        from app.db import get_supabase_client
        sb = get_supabase_client()
        sb.table("email_otps").update({"is_used": True}).eq("user_email", email_clean).eq("purpose", purpose).eq("is_used", False).execute()
        sb.table("email_otps").insert({
            "user_email": email_clean,
            "otp_hash": otp_hash,
            "purpose": purpose,
            "challenge_id": challenge_id,
            "expires_at": expires_at.isoformat(),
            "attempts": 0,
            "max_attempts": MAX_ATTEMPTS,
            "is_used": False
        }).execute()
        return True, challenge_id, None
    except Exception as exc:
        return False, "", str(exc)


def verify_stored_otp(user_email: str, entered_otp: str, purpose: str) -> tuple[bool, str]:
    """
    Verifies an entered 6-digit OTP against the active challenge in PostgreSQL `email_otps`.
    Enforces expiry, max attempts, and uses constant-time hmac comparison.
    Returns (True, "Success message") or (False, "Error message").
    """
    if not entered_otp or len(entered_otp.strip()) != 6 or not entered_otp.strip().isdigit():
        return False, "Please enter a valid 6-digit verification code."

    email_clean = user_email.strip().lower()
    conn = _get_pg_connection()

    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, otp_hash, challenge_id, expires_at, attempts, max_attempts
                FROM email_otps
                WHERE LOWER(user_email) = %s AND purpose = %s AND is_used = FALSE
                ORDER BY created_at DESC LIMIT 1;
                """,
                (email_clean, purpose)
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return False, "No active verification challenge found. Please request a new code."

            row_id, stored_hash, challenge_id, expires_at, attempts, max_attempts = row

            # Check attempt limit
            if attempts >= max_attempts:
                cur.execute("UPDATE email_otps SET is_used = TRUE WHERE id = %s;", (row_id,))
                conn.commit()
                cur.close()
                conn.close()
                return False, "Maximum attempts exceeded. Please request a new code."

            # Check expiration
            now_utc = datetime.now(timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now_utc > expires_at:
                cur.execute("UPDATE email_otps SET is_used = TRUE WHERE id = %s;", (row_id,))
                conn.commit()
                cur.close()
                conn.close()
                return False, "Verification code has expired. Please request a new code."

            # Compute candidate HMAC-SHA256 with pepper
            candidate_hash = hash_otp_hmac(entered_otp.strip(), challenge_id=challenge_id, purpose=purpose)

            # Constant-time comparison
            if hmac.compare_digest(candidate_hash, stored_hash):
                cur.execute(
                    "UPDATE email_otps SET is_used = TRUE, consumed_at = NOW() WHERE id = %s;",
                    (row_id,)
                )
                conn.commit()
                cur.close()
                conn.close()
                return True, "Verification successful."
            else:
                cur.execute("UPDATE email_otps SET attempts = attempts + 1 WHERE id = %s;", (row_id,))
                conn.commit()
                remaining = max(0, max_attempts - (attempts + 1))
                cur.close()
                conn.close()
                return False, f"Incorrect verification code. {remaining} attempt(s) remaining."
        except Exception as exc:
            try:
                conn.close()
            except Exception:
                pass
            return False, f"Verification service error: {exc}"

    # Supabase Client fallback
    try:
        from app.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("email_otps").select("*").eq("user_email", email_clean).eq("purpose", purpose).eq("is_used", False).order("created_at", desc=True).limit(1).execute()
        if not resp.data:
            return False, "No active verification challenge found. Please request a new code."

        record = resp.data[0]
        challenge_id = record["challenge_id"]
        stored_hash = record["otp_hash"]
        attempts = record.get("attempts", 0)
        max_attempts = record.get("max_attempts", MAX_ATTEMPTS)

        if attempts >= max_attempts:
            sb.table("email_otps").update({"is_used": True}).eq("id", record["id"]).execute()
            return False, "Maximum attempts exceeded. Please request a new code."

        candidate_hash = hash_otp_hmac(entered_otp.strip(), challenge_id=challenge_id, purpose=purpose)
        if hmac.compare_digest(candidate_hash, stored_hash):
            sb.table("email_otps").update({"is_used": True, "consumed_at": datetime.now(timezone.utc).isoformat()}).eq("id", record["id"]).execute()
            return True, "Verification successful."
        else:
            sb.table("email_otps").update({"attempts": attempts + 1}).eq("id", record["id"]).execute()
            remaining = max(0, max_attempts - (attempts + 1))
            return False, f"Incorrect verification code. {remaining} attempt(s) remaining."
    except Exception as exc:
        return False, f"Verification service error: {exc}"


def send_otp_email(recipient_email: str, otp_code: str, purpose: str = "Email Verification") -> tuple[bool, str | None]:
    """
    Sends a styled HTML email with the 6-digit OTP code using Gmail SMTP.
    Returns (True, None) on success, or (False, error_message) on failure.
    """
    smtp_user = os.environ.get("MAIL_USERNAME", "")
    smtp_pass = os.environ.get("MAIL_PASSWORD", "")
    smtp_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("MAIL_PORT", 587))
    use_tls = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")

    try:
        from flask import current_app
        if current_app:
            smtp_user = current_app.config.get("MAIL_USERNAME", smtp_user)
            smtp_pass = current_app.config.get("MAIL_PASSWORD", smtp_pass)
            smtp_server = current_app.config.get("MAIL_SERVER", smtp_server)
            smtp_port = int(current_app.config.get("MAIL_PORT", smtp_port))
            use_tls = current_app.config.get("MAIL_USE_TLS", use_tls)
    except Exception:
        pass

    if not smtp_user or not smtp_pass:
        return False, "SMTP credentials are not configured."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Smart Civic Guardian - {purpose} OTP Code"
    msg["From"] = f"Smart Civic Guardian <{smtp_user}>"
    msg["To"] = recipient_email

    text_body = (
        f"Smart Civic Guardian - {purpose}\n\n"
        f"Your 6-digit verification code is: {otp_code}\n\n"
        f"This code will expire in {OTP_EXPIRY_MINUTES} minutes.\n"
        "If you did not request this code, please ignore this email."
    )

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%); padding: 28px 24px; text-align: center; color: #ffffff; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
            .header p {{ margin: 6px 0 0; font-size: 14px; opacity: 0.9; }}
            .content {{ padding: 32px 28px; text-align: center; }}
            .otp-box {{ background: #f1f5f9; border: 2px dashed #0d6efd; border-radius: 10px; padding: 18px 24px; display: inline-block; margin: 20px 0; }}
            .otp-code {{ font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #0d6efd; font-family: monospace; }}
            .badge {{ display: inline-block; padding: 4px 10px; background: #e0f2fe; color: #0369a1; border-radius: 999px; font-size: 12px; font-weight: 600; margin-bottom: 12px; }}
            .note {{ font-size: 13px; color: #64748b; line-height: 1.6; margin-top: 16px; }}
            .footer {{ background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Smart Civic Guardian</h1>
                <p>Together for Cleaner, Safer &amp; Smarter Cities</p>
            </div>
            <div class="content">
                <div class="badge">{purpose.upper()}</div>
                <h2 style="margin: 0 0 10px; font-size: 20px; color: #1e293b;">Your Verification Code</h2>
                <p style="margin: 0 0 20px; font-size: 14px; color: #475569;">
                    Use the 6-digit code below to complete your {purpose.lower()}.
                </p>
                <div class="otp-box">
                    <span class="otp-code">{otp_code}</span>
                </div>
                <p class="note">
                    This code is valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong>.<br>
                    For security reasons, never share this verification code with anyone.
                </p>
            </div>
            <div class="footer">
                &copy; {datetime.now().year} Smart Civic Guardian. Automated message, do not reply.
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [recipient_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)
