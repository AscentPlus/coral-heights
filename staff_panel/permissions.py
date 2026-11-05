from functools import wraps
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render


def has_panel_access(user):
    """
    Returns True if user is superuser OR has a StaffProfile.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return hasattr(user, 'staff_profile')


def has_website_access(user):
    """
    Returns True if superuser OR staff_profile access_level is 'website' or 'both'.
    """
    if not has_panel_access(user):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'staff_profile', None)
    return profile is not None and profile.access_level in ('website', 'both')


def has_bookings_access(user):
    """
    Returns True if superuser OR staff_profile access_level is 'bookings' or 'both'.
    """
    if not has_panel_access(user):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'staff_profile', None)
    return profile is not None and profile.access_level in ('bookings', 'both')


def is_panel_superuser(user):
    """
    Returns True if user is an active superuser.
    """
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


def staff_login_required(view_func):
    """
    Decorator requiring user to be logged in and have panel access (superuser or StaffProfile).
    Redirects to /staff/login/?next=... if unauthenticated or unauthorized.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            login_url = reverse('staff_panel:login')
            next_url = request.get_full_path()
            return HttpResponseRedirect(f"{login_url}?next={next_url}")
        if not has_panel_access(request.user):
            login_url = reverse('staff_panel:login')
            return HttpResponseRedirect(login_url)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def website_access_required(view_func):
    """
    Decorator requiring website access permission.
    """
    @wraps(view_func)
    @staff_login_required
    def _wrapped_view(request, *args, **kwargs):
        if not has_website_access(request.user):
            return render(request, 'staff_panel/403.html', {'message': 'You do not have permission to access Website Content settings.'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def bookings_access_required(view_func):
    """
    Decorator requiring bookings access permission.
    """
    @wraps(view_func)
    @staff_login_required
    def _wrapped_view(request, *args, **kwargs):
        if not has_bookings_access(request.user):
            return render(request, 'staff_panel/403.html', {'message': 'You do not have permission to access Bookings & Guest Management.'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def superuser_required(view_func):
    """
    Decorator requiring superuser status (for Staff Management).
    """
    @wraps(view_func)
    @staff_login_required
    def _wrapped_view(request, *args, **kwargs):
        if not is_panel_superuser(request.user):
            return render(request, 'staff_panel/403.html', {'message': 'Superuser privilege is required for Staff Management.'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view
