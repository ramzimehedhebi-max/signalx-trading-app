"""
Stripe subscriptions module.
- Creates Customer + Checkout Session for monthly EUR 9.99 plan
- Handles webhooks to flip user.is_premium
- Idempotent on customer creation
"""
import os
import logging
import stripe
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "signalx://premium/success")
CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "signalx://premium/cancel")

stripe.api_key = STRIPE_SECRET


def is_configured() -> bool:
    """True if Stripe is properly configured with real keys (not placeholders)."""
    return (
        bool(STRIPE_SECRET)
        and STRIPE_SECRET.startswith("sk_")
        and "placeholder" not in STRIPE_SECRET
        and bool(STRIPE_PRICE_ID)
        and STRIPE_PRICE_ID.startswith("price_")
        and "placeholder" not in STRIPE_PRICE_ID
    )


async def get_or_create_customer(db, user: dict) -> str:
    """Return existing or new Stripe customer ID for a user."""
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]
    customer = stripe.Customer.create(
        email=user["email"],
        name=user.get("name"),
        metadata={"app_user_id": user["id"]},
    )
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"stripe_customer_id": customer.id}}
    )
    return customer.id


def create_checkout_session(
    customer_id: str,
    user_id: str,
    success_url: str = None,
    cancel_url: str = None,
) -> dict:
    """Create a Stripe Checkout Session in subscription mode.
    
    success_url / cancel_url are passed dynamically from the client so that
    the redirect works on Expo Go (exp://) as well as standalone apps (signalx://).
    """
    final_success = (success_url or SUCCESS_URL)
    if "{CHECKOUT_SESSION_ID}" not in final_success:
        sep = "&" if "?" in final_success else "?"
        final_success = final_success + sep + "session_id={CHECKOUT_SESSION_ID}"
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=final_success,
        cancel_url=cancel_url or CANCEL_URL,
        metadata={"app_user_id": user_id},
        # Allow promo codes
        allow_promotion_codes=True,
    )
    return {"url": session.url, "session_id": session.id}


def verify_webhook(payload: bytes, sig_header: str):
    """Verify a Stripe webhook event. Returns the parsed event or raises."""
    if not STRIPE_WEBHOOK_SECRET or "placeholder" in STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Stripe webhook secret not configured")
    return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)


def subscription_to_dict(sub) -> dict:
    """Compact representation we store in user doc."""
    return {
        "subscription_id": sub.id,
        "subscription_status": sub.status,
        "current_period_end": datetime.fromtimestamp(
            sub.current_period_end, tz=timezone.utc
        )
        if getattr(sub, "current_period_end", None)
        else None,
        "cancel_at_period_end": getattr(sub, "cancel_at_period_end", False),
    }


def is_premium_status(status: str) -> bool:
    """Active/trialing subscriptions grant premium access."""
    return status in ("active", "trialing")
