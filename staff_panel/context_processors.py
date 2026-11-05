from .permissions import has_website_access, has_bookings_access, is_panel_superuser


def staff_panel_context(request):
    """
    Context processor ensuring sidebar permissions are always available on all staff views.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    return {
        'has_website_access': has_website_access(request.user),
        'has_bookings_access': has_bookings_access(request.user),
        'is_panel_superuser': is_panel_superuser(request.user),
    }
