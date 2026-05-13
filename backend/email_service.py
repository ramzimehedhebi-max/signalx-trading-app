"""
Resend email service for SignalX.

- Sends transactional emails (e.g. password reset codes) via Resend.com
- Branded HTML template in French, dark theme matching the app
- Async (non-blocking) — failures are logged but never crash the caller
"""
import os
import logging
from typing import Optional
import resend

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_ADDR = os.environ.get("EMAIL_FROM", "SignalX <onboarding@resend.dev>")

if API_KEY:
    resend.api_key = API_KEY


def is_configured() -> bool:
    return bool(API_KEY) and API_KEY.startswith("re_")


def _reset_html(code: str, name: Optional[str] = None) -> str:
    greeting = f"Bonjour {name}," if name else "Bonjour,"
    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Code de réinitialisation SignalX</title>
</head>
<body style="margin:0;padding:0;background:#0B0B10;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#fff;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#0B0B10;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width:540px;background:#15151D;border-radius:20px;overflow:hidden;border:1px solid #2A2A35;">
        <!-- HEADER -->
        <tr><td style="padding:32px 28px 16px 28px;text-align:center;">
          <div style="display:inline-block;background:linear-gradient(135deg,#F3BA2F,#FFD75A);padding:14px 22px;border-radius:14px;">
            <span style="color:#0B0B10;font-weight:900;font-size:22px;letter-spacing:1px;">SignalX</span>
          </div>
        </td></tr>
        <!-- TITLE -->
        <tr><td style="padding:8px 28px 0 28px;text-align:center;">
          <h1 style="color:#fff;font-size:24px;font-weight:800;margin:14px 0 6px 0;letter-spacing:-0.5px;">🔐 Réinitialisation du mot de passe</h1>
          <p style="color:#9999A8;font-size:14px;margin:0;line-height:1.5;">{greeting}<br/>Voici ton code de récupération SignalX.</p>
        </td></tr>
        <!-- CODE BOX -->
        <tr><td style="padding:24px 28px;">
          <div style="background:#0B0B10;border:1px solid rgba(243,186,47,0.4);border-radius:16px;padding:28px 16px;text-align:center;">
            <div style="color:#F3BA2F;font-size:11px;letter-spacing:2.5px;font-weight:800;margin-bottom:10px;">CODE À 6 CHIFFRES</div>
            <div style="font-family:'SF Mono',Menlo,Consolas,monospace;color:#fff;font-size:42px;font-weight:900;letter-spacing:14px;line-height:1;">{code}</div>
            <div style="color:#666;font-size:11px;margin-top:14px;">Expire dans 30 minutes</div>
          </div>
        </td></tr>
        <!-- WARNING -->
        <tr><td style="padding:0 28px 8px 28px;">
          <div style="background:rgba(255,69,96,0.08);border:1px solid rgba(255,69,96,0.3);border-radius:12px;padding:14px 16px;color:#fff;font-size:13px;line-height:1.5;">
            <strong style="color:#FF6B85;">⚠️ Important</strong><br/>
            Ne partage <strong>jamais</strong> ce code, même avec le support SignalX. Si tu n'as pas demandé cette réinitialisation, ignore cet email — ton mot de passe reste inchangé.
          </div>
        </td></tr>
        <!-- HOW TO -->
        <tr><td style="padding:14px 28px 28px 28px;">
          <h3 style="color:#fff;font-size:14px;margin:6px 0 10px 0;font-weight:800;">📱 Comment l'utiliser</h3>
          <ol style="color:#bbb;font-size:13px;line-height:1.7;padding-left:18px;margin:0;">
            <li>Retourne sur l'app SignalX → écran <em>"Mot de passe oublié"</em></li>
            <li>Saisis ce code à 6 chiffres</li>
            <li>Choisis un nouveau mot de passe sécurisé</li>
          </ol>
        </td></tr>
        <!-- FOOTER -->
        <tr><td style="padding:18px 28px 24px 28px;border-top:1px solid #2A2A35;text-align:center;">
          <div style="color:#666;font-size:11px;line-height:1.6;">
            Cet email t'a été envoyé par <strong style="color:#F3BA2F;">SignalX</strong> — Trading IA pour Binance.<br/>
            Pour toute question : support@signalx.app
          </div>
        </td></tr>
      </table>
      <div style="color:#444;font-size:10px;margin-top:18px;">© 2026 SignalX. Aucune garantie de gain. Trading risqué.</div>
    </td></tr>
  </table>
</body></html>"""


async def send_reset_code_email(email: str, code: str, name: Optional[str] = None) -> bool:
    """Send the 6-digit password reset code by email. Returns True on success."""
    if not is_configured():
        logger.warning("[email] Resend not configured (RESEND_API_KEY missing)")
        return False
    try:
        # The Resend SDK v2 is sync; we run it in a thread to keep FastAPI async-safe.
        import asyncio
        params = {
            "from": FROM_ADDR,
            "to": [email],
            "subject": "🔐 Code de réinitialisation SignalX",
            "html": _reset_html(code, name),
            "reply_to": "support@signalx.app",
            "tags": [{"name": "type", "value": "password_reset"}],
        }
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: resend.Emails.send(params))
        logger.info(f"[email] reset code sent to={email} id={getattr(result, 'id', None) or result.get('id') if isinstance(result, dict) else result}")
        return True
    except Exception as e:
        logger.warning(f"[email] send_reset_code_email failed for {email}: {e}")
        return False
