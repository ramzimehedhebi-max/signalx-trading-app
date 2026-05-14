from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json, httpx, asyncio, uuid, logging

from core import db, get_current_user, BINANCE_BASE, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
from fastapi.responses import RedirectResponse, HTMLResponse
from models import PremiumCheckoutReq
import stripe_subs
from services.premium_svc import _get_premium_status

@router.get("/premium/status")
async def premium_status(user=Depends(get_current_user)):
    return await _get_premium_status(user["id"])



@router.post("/premium/checkout")
async def premium_checkout(req: PremiumCheckoutReq = None, user=Depends(get_current_user)):
    if not stripe_subs.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Paiements indisponibles — Stripe n'est pas encore configuré côté serveur.",
        )
    u = await db.users.find_one({"id": user["id"]})
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    try:
        customer_id = await stripe_subs.get_or_create_customer(db, u)
        sess = stripe_subs.create_checkout_session(
            customer_id,
            user["id"],
            success_url=(req.success_url if req else None),
            cancel_url=(req.cancel_url if req else None),
        )
        return sess
    except Exception as e:
        logger.exception(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)[:200]}")


@router.post("/premium/cancel")
async def premium_cancel(user=Depends(get_current_user)):
    """Cancel at period end (user keeps access until end of paid period)."""
    if not stripe_subs.is_configured():
        raise HTTPException(status_code=503, detail="Stripe non configuré")
    u = await db.users.find_one({"id": user["id"]})
    if not u or not u.get("subscription_id"):
        raise HTTPException(status_code=400, detail="Aucun abonnement actif")
    try:
        import stripe
        sub = stripe.Subscription.modify(u["subscription_id"], cancel_at_period_end=True)
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"cancel_at_period_end": True}},
        )
        return {"ok": True, "cancel_at_period_end": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ----- Stripe HTTPS bridge → deep-link back into Expo app -----
# Chrome blocks direct exp:// redirects from HTTPS, so Stripe redirects HERE first,
# this page does a JS deep-link to the app scheme.
from fastapi.responses import HTMLResponse

_BRIDGE_HTML = """<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Retour à SignalX…</title>
<style>
  html,body{margin:0;background:#0B0B10;color:#fff;font-family:-apple-system,Segoe UI,Roboto,sans-serif;height:100%;}
  .wrap{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;text-align:center;gap:16px;}
  .check{width:84px;height:84px;border-radius:50%;background:rgba(0,227,150,0.15);border:2px solid rgba(0,227,150,0.4);display:flex;align-items:center;justify-content:center;font-size:48px;color:#00E396;}
  .cancel{width:84px;height:84px;border-radius:50%;background:rgba(255,69,96,0.12);border:2px solid rgba(255,69,96,0.35);display:flex;align-items:center;justify-content:center;font-size:48px;color:#FF4560;}
  h1{font-size:24px;margin:0;font-weight:900;}
  p{color:#bbb;margin:0;font-size:15px;max-width:320px;line-height:1.55;}
  .hint{background:rgba(243,186,47,0.12);border:1px solid rgba(243,186,47,0.35);padding:14px 16px;border-radius:14px;font-size:14px;color:#fff;max-width:340px;line-height:1.5;}
  .hint b{color:#F3BA2F;}
  a.btn{display:inline-block;padding:14px 26px;background:#F3BA2F;color:#000;font-weight:800;border-radius:999px;text-decoration:none;font-size:15px;}
  .small{color:#666;font-size:12px;margin-top:8px;line-height:1.5;}
</style>
</head><body>
<div class="wrap">
  <div class="__ICON_CLASS__">__ICON__</div>
  <h1>__TITLE__</h1>
  <p>__MSG__</p>
  <div class="hint">
    👉 <b>Ferme cet onglet</b> et reviens dans l'app SignalX.<br/>
    L'activation est automatique sur ton compte.
  </div>
  <a id="back" class="btn" href="__DEEPLINK__">Retour à SignalX</a>
  <div class="small">Astuce : appuie sur la flèche "retour" de ton téléphone<br/>pour revenir directement dans l'app.</div>
</div>
<script>
  var DEEPLINK = "__DEEPLINK__";
  // Try to deep-link automatically right away
  setTimeout(function(){ try { window.location.href = DEEPLINK; } catch(e){} }, 300);
  document.body.addEventListener('click', function(){ try { window.location.href = DEEPLINK; } catch(e){} });
</script>
</body></html>"""


@router.get("/stripe/return")
async def stripe_return(
    paid: str = "1",
    target: str = "",
    session_id: str = "",
):
    """HTTPS bridge: Stripe redirects HERE → this page deep-links to the app via JS.
    `target` is a URL-encoded deep link like exp://...../premium that we relay to.
    """
    import urllib.parse
    deeplink = urllib.parse.unquote(target) if target else "signalx://premium"
    sep = "&" if "?" in deeplink else "?"
    deeplink = f"{deeplink}{sep}paid={paid}"
    if session_id:
        deeplink += f"&session_id={urllib.parse.quote(session_id)}"
    if paid == "1":
        title = "Paiement reçu !"
        msg = "Ton abonnement Premium SignalX est en cours d'activation. Cela prend environ 5 à 15 secondes."
        icon_class = "check"
        icon = "✓"
    else:
        title = "Paiement annulé"
        msg = "Aucun montant n'a été débité. Tu peux réessayer à tout moment depuis l'app."
        icon_class = "cancel"
        icon = "✕"
    html = (
        _BRIDGE_HTML
        .replace("__TITLE__", title)
        .replace("__MSG__", msg)
        .replace("__ICON__", icon)
        .replace("__ICON_CLASS__", icon_class)
        .replace("__DEEPLINK__", deeplink)
    )
    return HTMLResponse(content=html)


# NOTE: webhook is mounted on the main app (not api_router) to keep the raw body
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe_subs.verify_webhook(payload, sig)
    except Exception as e:
        logger.warning(f"Stripe webhook verify failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    etype = event["type"]
    obj = event["data"]["object"]
    customer_id = obj.get("customer")
    user_doc = None
    if customer_id:
        user_doc = await db.users.find_one({"stripe_customer_id": customer_id})

    try:
        if etype in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            sub = obj
            if user_doc:
                upd = {
                    "subscription_id": sub.get("id"),
                    "subscription_status": sub.get("status"),
                    "current_period_end": datetime.fromtimestamp(
                        sub.get("current_period_end"), tz=timezone.utc
                    )
                    if sub.get("current_period_end")
                    else None,
                    "cancel_at_period_end": sub.get("cancel_at_period_end", False),
                    "premium_updated_at": datetime.now(timezone.utc),
                }
                await db.users.update_one({"id": user_doc["id"]}, {"$set": upd})
                # Notify
                if etype == "customer.subscription.created":
                    await _create_notification(
                        user_doc["id"],
                        "premium",
                        "🎉 Bienvenue dans Premium !",
                        "Tu as maintenant accès aux paires illimitées, prédictions illimitées et trading Live.",
                    )
                elif etype == "customer.subscription.deleted":
                    await _create_notification(
                        user_doc["id"],
                        "premium",
                        "❌ Abonnement Premium annulé",
                        "Tu repasses en plan Free. Tu peux te réabonner à tout moment.",
                    )
        elif etype == "invoice.payment_failed":
            if user_doc:
                await db.users.update_one(
                    {"id": user_doc["id"]},
                    {"$set": {"subscription_status": "past_due"}},
                )
                await _create_notification(
                    user_doc["id"],
                    "premium",
                    "⚠️ Paiement Premium échoué",
                    "Le paiement de ton abonnement Premium n'a pas pu être traité. Mets à jour ta carte sur Stripe.",
                )
        elif etype == "checkout.session.completed":
            # Initial activation; the subscription.created event will set details
            logger.info(f"Stripe checkout completed for customer={customer_id}")
    except Exception as e:
        logger.exception(f"Stripe webhook handler error: {e}")
    return {"received": True}
