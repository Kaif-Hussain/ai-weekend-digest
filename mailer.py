import os
import smtplib
import ssl
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()
RAW_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
GMAIL_APP_PASSWORD = RAW_PASSWORD.replace(" ", "").replace("_", "").strip()


def build_email_html(day_label: str, rank_badge: str, item: dict) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background-color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#f8fafc;">
      <table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
        <tr>
          <td align="center">
            <table width="600" cellpadding="0" cellspacing="0" style="background-color:#1e293b;border-radius:16px;border:1px solid #334155;overflow:hidden;">
              <tr>
                <td style="padding:28px 32px;background:linear-gradient(135deg,#4f46e5,#0ea5e9);">
                  <span style="display:inline-block;padding:4px 12px;background:rgba(255,255,255,0.2);border-radius:999px;font-size:12px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#ffffff;">
                    {day_label} EDITION &bull; {rank_badge}
                  </span>
                  <h1 style="margin:12px 0 0;font-size:24px;line-height:1.3;color:#ffffff;">
                    {item.get('title', 'AI Weekly Breakthrough')}
                  </h1>
                </td>
              </tr>
              <tr>
                <td style="padding:28px 32px;">
                  <p style="margin:0 0 8px;font-size:12px;font-weight:700;color:#38bdf8;text-transform:uppercase;">
                    Category: {item.get('category', 'AI Tech')}
                  </p>
                  <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#e2e8f0;">
                    {item.get('summary', '')}
                  </p>
                  <div style="background-color:#0f172a;border-left:4px solid #6366f1;padding:16px;border-radius:8px;margin-bottom:20px;">
                    <p style="margin:0 0 6px;font-size:13px;font-weight:700;color:#a5b4fc;">WHY IT MATTERS</p>
                    <p style="margin:0;font-size:14px;line-height:1.5;color:#cbd5e1;">{item.get('why_it_matters', '')}</p>
                  </div>
                  <div style="background-color:#0f172a;border-left:4px solid #10b981;padding:16px;border-radius:8px;margin-bottom:24px;">
                    <p style="margin:0 0 6px;font-size:13px;font-weight:700;color:#6ee7b7;">QUICK START</p>
                    <p style="margin:0;font-size:14px;line-height:1.5;color:#cbd5e1;">{item.get('quick_start', '')}</p>
                  </div>
                  <a href="{item.get('source_url', '#')}" style="display:inline-block;padding:12px 24px;background-color:#4f46e5;color:#ffffff;text-decoration:none;font-weight:600;border-radius:8px;font-size:14px;">
                    Read Official Source &rarr;
                  </a>
                </td>
              </tr>
              <tr>
                <td style="padding:16px 32px;background-color:#0f172a;text-align:center;font-size:12px;color:#64748b;">
                  Powered by Google ADK &bull; BYOK AI Weekly Digest
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def send_weekend_email(to_email: str, day_label: str, rank_badge: str, item: dict):
    subject = f"[{day_label} AI Pick] {item.get('title', 'Top AI News of the Week')}"
    html_content = build_email_html(day_label, rank_badge, item)

    if not SENDER_EMAIL:
        raise RuntimeError("SENDER_EMAIL is missing in environment variables.")

    # Primary: Brevo HTTPS API (Port 443 — bypasses Railway SMTP blocks & sends to any friend)
    if BREVO_API_KEY:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": BREVO_API_KEY,
                "content-type": "application/json",
            },
            json={
                "sender": {"name": "AI Weekend Digest", "email": SENDER_EMAIL},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content,
            },
            timeout=20,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Brevo API Error ({response.status_code}): {response.text}")
        return

    # Fallback: Local Gmail SMTP (for local testing when BREVO_API_KEY is not set)
    if not GMAIL_APP_PASSWORD:
        raise RuntimeError("Set BREVO_API_KEY (for Railway) or GMAIL_APP_PASSWORD (for local SMTP).")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"AI Weekend Digest <{SENDER_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())