import logging
from django.http import JsonResponse
from django.shortcuts import redirect
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from content.models import ContactInformation
from bookings.views import get_client_ip
from .forms import EnquiryForm
from .models import Enquiry

logger = logging.getLogger(__name__)


def send_enquiry_notification(enquiry: Enquiry):
    """
    Attempts to send email notification for an enquiry.
    Updates enquiry.notification_sent and notification_error atomically.
    Returns (success: bool, error_msg: str).
    """
    try:
        contact_info = ContactInformation.objects.first()
        recipient_email = contact_info.email if (contact_info and contact_info.email) else 'info@hotelcoralheights.com'

        subject = f"New Catering & Event Enquiry: {enquiry.get_function_type_display()} ({enquiry.contact_name})"
        message = (
            f"A new event enquiry has been submitted on Hotel Coral Heights website:\n\n"
            f"• Contact Name: {enquiry.contact_name}\n"
            f"• Contact Phone: {enquiry.contact_phone}\n"
            f"• Function Type: {enquiry.get_function_type_display()}\n"
            f"• Preferred Date: {enquiry.preferred_date}\n"
            f"• Expected Guests: {enquiry.guest_count}\n"
            f"• Food / Menu Requests: {enquiry.menu_requirements or 'None'}\n"
            f"• Additional Notes: {enquiry.notes or 'None'}\n\n"
            f"Submitted at: {enquiry.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@hotelcoralheights.com')
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        enquiry.notification_sent = True
        enquiry.notification_error = ''
        enquiry.save(update_fields=['notification_sent', 'notification_error'])
        return True, ""
    except Exception as exc:
        logger.warning("Failed to send enquiry notification email: %s", exc)
        enquiry.notification_sent = False
        enquiry.notification_error = str(exc)
        enquiry.save(update_fields=['notification_sent', 'notification_error'])
        return False, str(exc)


def submit_enquiry(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    accept_header = request.headers.get('Accept', '')
    is_browser_html_submit = ('text/html' in accept_header) and (
        request.headers.get('X-Requested-With') != 'XMLHttpRequest'
    )

    # Rate limiting: max 5 submissions per hour (3600 seconds) per IP
    client_ip = get_client_ip(request)
    ip_cache_key = f"enquiry_throttle_{client_ip}" if client_ip else None
    if ip_cache_key:
        curr_count = None
        try:
            curr_count = cache.get(ip_cache_key)
        except Exception as e:
            logger.warning("Cache unavailable for enquiry throttle check: %s", e)

        if curr_count is not None and curr_count >= 5:
            msg = 'Too many enquiry submissions from this network. Please wait a while or contact us directly.'
            if is_browser_html_submit:
                request.session['enquiry_errors'] = {'non_field_errors': [msg]}
                return redirect('/#enquiry')
            return JsonResponse({'success': False, 'error': msg}, status=429)

    form = EnquiryForm(request.POST)

    if form.is_valid():
        enquiry = form.save()

        # Update rate limit counter atomically
        if ip_cache_key:
            try:
                if cache.get(ip_cache_key) is None:
                    cache.set(ip_cache_key, 1, timeout=3600)
                else:
                    try:
                        cache.incr(ip_cache_key)
                    except ValueError:
                        cache.set(ip_cache_key, 1, timeout=3600)
            except Exception as e:
                logger.warning("Cache unavailable for enquiry throttle update: %s", e)

        # Send notification (saved enquiry is preserved even if notification delivery fails)
        send_enquiry_notification(enquiry)

        if is_browser_html_submit:
            return redirect('/?submitted=true#enquiry')
        else:
            return JsonResponse({
                'success': True,
                'message': 'Thank you! Your enquiry has been received. We will contact you shortly.'
            })
    else:
        errors = {}
        for field, error_list in form.errors.get_json_data().items():
            errors[field] = [e['message'] for e in error_list]

        if is_browser_html_submit:
            request.session['enquiry_errors'] = errors
            request.session['enquiry_data'] = request.POST.dict()
            return redirect('/#enquiry')
        else:
            return JsonResponse({'success': False, 'errors': errors}, status=400)
