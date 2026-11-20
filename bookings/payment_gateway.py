import uuid
import logging
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class BasePaymentGateway:
    """Provider-neutral payment gateway interface."""

    def create_order(self, booking):
        raise NotImplementedError

    def confirm_payment(self, booking, payment_data=None):
        raise NotImplementedError

    def verify_payment_notification(self, payload: dict, signature: str = None) -> dict:
        """
        Verifies provider signature, amount, currency, and booking reference.
        Returns verified dict with booking_id, payment_reference, amount, currency, status.
        """
        raise NotImplementedError

    def process_refund(self, booking, amount=None, reason="Guest Cancellation") -> dict:
        """Hook for initiating gateway refunds."""
        raise NotImplementedError


class MockPaymentGateway(BasePaymentGateway):
    """
    Development & testing mock payment gateway.
    Strictly disabled in production unless ALLOW_MOCK_PAYMENT is explicitly enabled.
    """

    def __init__(self):
        self._verify_environment()

    def _verify_environment(self):
        if not getattr(settings, 'DEBUG', False) and not getattr(settings, 'ALLOW_MOCK_PAYMENT', False):
            raise ImproperlyConfigured(
                "MockPaymentGateway cannot be used when DEBUG is False unless "
                "ALLOW_MOCK_PAYMENT is explicitly set to True."
            )

    def create_order(self, booking):
        self._verify_environment()
        nights = (booking.check_out - booking.check_in).days
        total_amount = booking.room.room_type.base_price_per_night * nights
        return {
            "order_id": f"mock_order_{booking.id}",
            "amount": float(total_amount),
            "currency": "INR"
        }

    def confirm_payment(self, booking, payment_data=None):
        self._verify_environment()
        payment_ref = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        logger.info(f"[MOCK PAYMENT] Payment confirmed for booking #{booking.id} ({payment_ref})")
        return payment_ref

    def verify_payment_notification(self, payload: dict, signature: str = None) -> dict:
        self._verify_environment()
        booking_id = payload.get("booking_id")
        amount = Decimal(str(payload.get("amount", "0")))
        currency = payload.get("currency", "INR")
        payment_ref = payload.get("payment_reference") or f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        return {
            "verified": True,
            "booking_id": booking_id,
            "payment_reference": payment_ref,
            "amount": amount,
            "currency": currency,
            "status": "PAID"
        }

    def process_refund(self, booking, amount=None, reason="Guest Cancellation") -> dict:
        self._verify_environment()
        refund_ref = f"REF-{uuid.uuid4().hex[:10].upper()}"
        logger.info(f"[MOCK REFUND] Refund processed for booking #{booking.id} ({refund_ref})")
        return {
            "success": True,
            "refund_reference": refund_ref,
            "amount": amount or booking.total_amount,
            "reason": reason
        }


def get_payment_gateway():
    gateway_name = getattr(settings, 'PAYMENT_GATEWAY', 'mock')
    is_prod = not getattr(settings, 'DEBUG', False)
    allow_mock = getattr(settings, 'ALLOW_MOCK_PAYMENT', False)

    if gateway_name == 'mock':
        if is_prod and not allow_mock:
            raise ImproperlyConfigured(
                "Mock payment gateway is rejected in production. Please configure a live payment provider."
            )
        return MockPaymentGateway()

    # Reject unknown or demo gateways in production
    if is_prod:
        raise ImproperlyConfigured(
            f"Unsupported or unconfigured payment gateway '{gateway_name}' in production."
        )

    return MockPaymentGateway()
