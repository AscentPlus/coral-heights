"""
Booking app context processor — makes shared constants available to all templates.
"""
from .constants import CANCELLATION_POLICY


def booking_constants(request):
    """
    Injects shared booking constants into the template context.
    Keeps the cancellation policy wording in one place (constants.py)
    rather than duplicated in views or templates.
    """
    return {
        'cancellation_policy': CANCELLATION_POLICY,
    }
