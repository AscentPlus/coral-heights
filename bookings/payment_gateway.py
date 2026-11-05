import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class MockPaymentGateway:
    """
    Placeholder payment gateway. Simulates an always-successful
    payment. Swap for RazorpayGateway once the merchant account is
    live — implement the same create_order(booking) / confirm_payment(booking)
    interface so the views calling it don't need to change, only which
    class settings.PAYMENT_GATEWAY resolves to.
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
        import uuid
        payment_ref = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        logger.info(
            f"[MOCK PAYMENT] Payment confirmed for booking #{booking.id} ({payment_ref})")
        return payment_ref


def get_payment_gateway():
    gateway_name = getattr(settings, 'PAYMENT_GATEWAY', 'mock')
    if gateway_name == 'mock':
        return MockPaymentGateway()
    # Plug in future gateways here (e.g. 'razorpay': RazorpayGateway())
    return MockPaymentGateway()
