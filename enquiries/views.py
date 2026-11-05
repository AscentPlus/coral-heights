from django.http import JsonResponse
from django.shortcuts import redirect
from django.core.mail import send_mail
from django.conf import settings
from content.models import ContactInformation
from .forms import EnquiryForm


def submit_enquiry(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    form = EnquiryForm(request.POST)
    accept_header = request.headers.get('Accept', '')
    is_browser_html_submit = ('text/html' in accept_header) and (
        request.headers.get('X-Requested-With') != 'XMLHttpRequest')

    if form.is_valid():
        enquiry = form.save()

        # Send email notification to hotel recipient address
        try:
            contact_info = ContactInformation.objects.first()
            recipient_email = contact_info.email if contact_info else 'info@hotelcoralheights.com'

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
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL',
                                 'noreply@hotelcoralheights.com')
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[recipient_email],
                fail_silently=True,
            )
        except Exception:
            pass

        if is_browser_html_submit:
            return redirect('/?submitted=true#enquiry')
        else:
            return JsonResponse({
                'success': True,
                'message': 'Thank you! Your enquiry has been received. We will contact you shortly.'
            })
    else:
        if is_browser_html_submit:
            return redirect('/#enquiry')
        else:
            errors = {}
            for field, error_list in form.errors.get_json_data().items():
                errors[field] = [e['message'] for e in error_list]
            return JsonResponse({'success': False, 'errors': errors}, status=400)
