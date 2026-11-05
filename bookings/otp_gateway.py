import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class ConsoleOTPGateway:
    """
    Dev/mock OTP gateway — logs the code instead of sending an SMS.
    Swap for a real provider (Gupshup/Interakt/Twilio/etc.) later by
    implementing the same send(phone, code) interface and pointing
    OTP_GATEWAY at it in settings.
    """

    def send(self, phone, code):
        logger.info(
            f"[MOCK OTP] Would send SMS to {phone}: your Coral Heights verification code is {code}")
        print(
            f"[MOCK OTP] Would send SMS to {phone}: your Coral Heights verification code is {code}")


def get_otp_gateway():
    gateway_name = getattr(settings, 'OTP_GATEWAY', 'console')
    if gateway_name == 'console':
        return ConsoleOTPGateway()
    # Plug in future gateways here (e.g. 'twilio': TwilioOTPGateway())
    return ConsoleOTPGateway()
