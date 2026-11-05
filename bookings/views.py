from staff_panel.permissions import has_bookings_access
import json
import secrets
from datetime import datetime, timedelta
from django.http import JsonResponse, Http404, HttpResponse
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.db import transaction
from django.core.cache import cache
from content.models import RoomType, Room
from .models import Guest, Booking, PhoneOTP
from .services import get_available_rooms, get_available_rooms_count
from .otp_gateway import get_otp_gateway
from .payment_gateway import get_payment_gateway
from .constants import CANCELLATION_POLICY


def parse_post_data(request):
    if request.content_type == 'application/json' and request.body:
        try:
            return json.loads(request.body)
        except Exception:
            pass
    return request.POST


def parse_date_input(date_str):
    """
    Parses a date string supporting both YYYY-MM-DD and DD-MM-YYYY formats.
    """
    if not date_str:
        raise ValueError("Empty date string")
    for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    raise ValueError(f"Invalid date format: {date_str}")


def format_date_dmy(date_val):
    """
    Formats a date object or date string into DD-MM-YYYY format.
    """
    if not date_val:
        return ''
    if hasattr(date_val, 'strftime'):
        return date_val.strftime('%d-%m-%Y')
    try:
        return parse_date_input(date_val).strftime('%d-%m-%Y')
    except (ValueError, TypeError):
        return str(date_val)


def check_availability(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    room_type_slug = request.GET.get('room_type', '').strip()
    check_in_str = request.GET.get('check_in', '').strip()
    check_out_str = request.GET.get('check_out', '').strip()

    if not room_type_slug or not check_in_str or not check_out_str:
        return JsonResponse(
            {'error': 'Please select dates and a room type.'},
            status=400
        )

    try:
        check_in = parse_date_input(check_in_str)
        check_out = parse_date_input(check_out_str)
    except ValueError:
        return JsonResponse(
            {'error': 'Invalid date format. Please use DD-MM-YYYY or YYYY-MM-DD.'},
            status=400
        )

    today = timezone.now().date()
    if check_in < today:
        return JsonResponse(
            {'error': 'Check-in date cannot be in the past.'},
            status=400
        )

    if check_out <= check_in:
        return JsonResponse(
            {'error': 'Check-out date must be after check-in date.'},
            status=400
        )

    try:
        room_type = RoomType.objects.get(slug=room_type_slug)
    except RoomType.DoesNotExist:
        return JsonResponse(
            {'error': 'Selected room type does not exist.'},
            status=400
        )

    # Validate guest bounds & room capacity if provided
    adults_raw = request.GET.get('adults')
    children_raw = request.GET.get('children')
    if adults_raw is not None or children_raw is not None:
        try:
            adults = int(adults_raw) if adults_raw is not None else 1
            children = int(children_raw) if children_raw is not None else 0
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Adults and children must be valid numbers.'}, status=400)

        if adults < 1:
            return JsonResponse({'error': 'Adults must be at least 1.'}, status=400)
        if children < 0:
            return JsonResponse({'error': 'Children cannot be negative.'}, status=400)

        if (adults + children) > room_type.max_occupancy:
            return JsonResponse({
                'error': f'Total guests ({adults + children}) exceed maximum capacity of {room_type.max_occupancy} for {room_type.name}.'
            }, status=400)

    available_count = get_available_rooms_count(room_type, check_in, check_out)
    nights = (check_out - check_in).days

    return JsonResponse({
        'available': available_count > 0,
        'count': available_count,
        'room_type_name': room_type.name,
        'price_per_night': f"{room_type.base_price_per_night:.2f}",
        'nights': nights
    })


def get_client_ip(request):
    """
    Extract client IP from env-configured header (e.g., HTTP_CF_CONNECTING_IP, HTTP_X_FORWARDED_FOR)
    or fall back to REMOTE_ADDR. When parsing multi-hop headers like X-Forwarded-For,
    trust the last hop appended by the trusted reverse proxy rather than client-controlled first values.
    """
    header_name = getattr(settings, 'CLIENT_IP_HEADER', 'HTTP_X_FORWARDED_FOR')
    if header_name:
        raw_val = request.META.get(header_name, '').strip()
        if raw_val:
            hops = [h.strip() for h in raw_val.split(',') if h.strip()]
            if hops:
                return hops[-1]
    return request.META.get('REMOTE_ADDR', '').strip()


def send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    data = parse_post_data(request)
    phone = str(data.get('phone', '')).strip()

    if not phone or not phone.replace('+', '').isdigit() or len(phone.replace('+', '')) < 10:
        return JsonResponse({'success': False, 'error': 'Please enter a valid 10-digit phone number.'}, status=400)

    # Rate limiting: max 5 sends per IP per 10 minutes (600 seconds)
    client_ip = get_client_ip(request)
    ip_cache_key = None
    ip_count = None
    if client_ip:
        ip_cache_key = f"otp_ratelimit_ip_{client_ip}"
        ip_count = cache.get(ip_cache_key)
        if ip_count is not None and ip_count >= 5:
            return JsonResponse({
                'success': False,
                'error': 'Too many verification code requests from this network. Please wait 10 minutes.'
            }, status=429)

    now = timezone.now()

    # Rate limiting: check if non-expired OTP for this phone was created < 30 seconds ago
    recent_otp = PhoneOTP.objects.filter(
        phone=phone).order_by('-created_at').first()
    if recent_otp and (now - recent_otp.created_at).total_seconds() < 30:
        return JsonResponse({'success': False, 'error': 'Please wait 30 seconds before requesting another code.'}, status=429)

    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = now + timedelta(minutes=5)

    PhoneOTP.objects.create(
        phone=phone,
        code=code,
        expires_at=expires_at,
        attempts=0,
        is_verified=False
    )

    if ip_cache_key:
        if ip_count is None:
            cache.set(ip_cache_key, 1, timeout=600)
        else:
            try:
                cache.incr(ip_cache_key)
            except ValueError:
                cache.set(ip_cache_key, 1, timeout=600)

    otp_gateway = get_otp_gateway()
    otp_gateway.send(phone, code)

    res_payload = {
        'success': True,
        'cooldown_seconds': 30
    }
    if getattr(settings, 'DEBUG', False) or getattr(settings, 'DEMO_SHOW_OTP', False):
        res_payload['debug_otp'] = code

    return JsonResponse(res_payload)


def verify_and_hold(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    data = parse_post_data(request)

    phone = str(data.get('phone', '')).strip()
    code = str(data.get('code', '')).strip()
    guest_name = str(data.get('guest_name', '')).strip()
    guest_email = str(data.get('guest_email', '')).strip() or None
    room_type_slug = str(data.get('room_type', '')).strip()
    check_in_str = str(data.get('check_in', '')).strip()
    check_out_str = str(data.get('check_out', '')).strip()

    try:
        adults = int(data.get('adults', 1))
        children = int(data.get('children', 0))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Adults and children must be valid numbers.'}, status=400)

    if adults < 1:
        return JsonResponse({'success': False, 'error': 'Adults must be at least 1.'}, status=400)
    if children < 0:
        return JsonResponse({'success': False, 'error': 'Children cannot be negative.'}, status=400)

    if not phone or not code or not guest_name or not room_type_slug or not check_in_str or not check_out_str:
        return JsonResponse({'success': False, 'error': 'All required fields must be provided.'}, status=400)

    now = timezone.now()

    # Find unverified PhoneOTP for phone
    otp = PhoneOTP.objects.filter(
        phone=phone, is_verified=False).order_by('-created_at').first()
    if not otp or otp.expires_at <= now:
        return JsonResponse({'success': False, 'error': 'OTP code has expired or is invalid. Please request a new code.'}, status=400)

    if otp.attempts >= 5:
        return JsonResponse({'success': False, 'error': 'Too many failed attempts. Please request a new code.'}, status=429)

    if otp.code != code:
        otp.attempts += 1
        otp.save()
        remaining = max(0, 5 - otp.attempts)
        if remaining == 0:
            return JsonResponse({'success': False, 'error': 'Too many failed attempts. Please request a new code.'}, status=429)
        return JsonResponse({'success': False, 'error': f'Invalid code. {remaining} attempt{"s" if remaining > 1 else ""} remaining.'}, status=400)

    # Validate dates
    try:
        check_in = parse_date_input(check_in_str)
        check_out = parse_date_input(check_out_str)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid date format. Please use DD-MM-YYYY or YYYY-MM-DD.'}, status=400)

    if check_in < now.date() or check_out <= check_in:
        return JsonResponse({'success': False, 'error': 'Invalid date selection.'}, status=400)

    try:
        room_type = RoomType.objects.get(slug=room_type_slug)
    except RoomType.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Selected room type does not exist.'}, status=400)

    # Enforce max occupancy bounds server-side
    if (adults + children) > room_type.max_occupancy:
        return JsonResponse({
            'success': False,
            'error': f'Total guests ({adults + children}) exceed maximum capacity of {room_type.max_occupancy} for {room_type.name}.'
        }, status=400)

    with transaction.atomic():
        # Evaluate queryset to acquire row locks on candidate rooms
        list(Room.objects.select_for_update().filter(room_type=room_type))

        # Re-check availability right now against locked candidate rooms
        available_rooms = get_available_rooms(room_type, check_in, check_out)
        if not available_rooms.exists():
            return JsonResponse(
                {'success': False, 'error': 'Sorry, this room type just sold out for these dates. Please search for alternative options.'},
                status=409
            )

        room = available_rooms.first()

        # Mark OTP verified now that room hold is guaranteed
        otp.is_verified = True
        otp.save()

        # Guest lookup / creation
        guest, created = Guest.objects.get_or_create(
            phone=phone,
            defaults={'name': guest_name, 'email': guest_email}
        )
        if not created:
            if guest_name and guest.name != guest_name:
                guest.name = guest_name
            if guest_email is not None and guest.email != guest_email:
                guest.email = guest_email
            guest.save()

        nights = (check_out - check_in).days
        total_amount = room_type.base_price_per_night * nights
        hold_expires_at = now + timedelta(minutes=15)

        booking = Booking.objects.create(
            room=room,
            guest=guest,
            check_in=check_in,
            check_out=check_out,
            adults=adults,
            children=children,
            status=Booking.STATUS_HELD,
            hold_expires_at=hold_expires_at,
            total_amount=total_amount
        )

    return JsonResponse({
        'success': True,
        'booking_id': booking.id,
        'payment_token': booking.access_token,
        'booking_reference': f"CH-{booking.id:05d}",
        'room_type_name': room_type.name,
        'check_in': check_in.strftime('%Y-%m-%d'),
        'check_out': check_out.strftime('%Y-%m-%d'),
        'check_in_display': check_in.strftime('%d-%m-%Y'),
        'check_out_display': check_out.strftime('%d-%m-%Y'),
        'nights': nights,
        'price_per_night': f"{room_type.base_price_per_night:.2f}",
        'total_amount': f"{total_amount:.2f}",
        'hold_expires_at': hold_expires_at.isoformat()
    })


def mock_pay(request, booking_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    data = parse_post_data(request)
    payment_token = (
        data.get('payment_token')
        or request.headers.get('X-Payment-Token')
        or request.GET.get('payment_token', '')
    )

    now = timezone.now()
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(id=booking_id)
        except Booking.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Booking not found.'}, status=404)

        if not payment_token or payment_token != booking.access_token:
            return JsonResponse({'success': False, 'error': 'Invalid or missing payment token.'}, status=403)

        if booking.status != Booking.STATUS_HELD or not booking.hold_expires_at or booking.hold_expires_at <= now:
            return JsonResponse(
                {'success': False, 'error': 'Hold has expired or booking is no longer held. Please start again.'},
                status=400
            )

        payment_gateway = get_payment_gateway()
        payment_ref = payment_gateway.confirm_payment(booking)

        if payment_ref:
            booking.status = Booking.STATUS_CONFIRMED
            booking.hold_expires_at = None
            booking.payment_reference = payment_ref
            booking.paid_at = now
            booking.save()

            nights = (booking.check_out - booking.check_in).days
            total_amount = booking.total_amount if booking.total_amount is not None else (
                booking.room.room_type.base_price_per_night * nights)
            receipt_url = reverse('bookings:receipt', kwargs={
                                  'booking_id': booking.id, 'token': booking.access_token})
            receipt_pdf_url = reverse('bookings:receipt_pdf', kwargs={
                                      'booking_id': booking.id, 'token': booking.access_token})

            return JsonResponse({
                'success': True,
                'booking_reference': f"CH-{booking.id:05d}",
                'room_type_name': booking.room.room_type.name,
                'check_in': booking.check_in.strftime('%Y-%m-%d'),
                'check_out': booking.check_out.strftime('%Y-%m-%d'),
                'check_in_display': booking.check_in.strftime('%d-%m-%Y'),
                'check_out_display': booking.check_out.strftime('%d-%m-%Y'),
                'nights': nights,
                'total_amount': f"{total_amount:.2f}",
                'payment_reference': payment_ref,
                'receipt_url': receipt_url,
                'receipt_pdf_url': receipt_pdf_url,
            })
        else:
            return JsonResponse({'success': False, 'error': 'Payment failed. Please try again.'}, status=400)



def _check_receipt_access(request, booking, token):
    """
    Shared access-control check for both HTML and PDF receipt views.
    Returns True if access is permitted, False otherwise.

    Access is granted if:
    - The user is authenticated and has bookings-panel access (staff bypass), OR
    - The provided token matches the booking's access_token.
    """
    is_staff_viewer = request.user.is_authenticated and has_bookings_access(
        request.user)
    return is_staff_viewer or token == booking.access_token


def view_receipt(request, booking_id, token):
    booking = get_object_or_404(Booking, id=booking_id)

    if not _check_receipt_access(request, booking, token):
        raise Http404()

    if booking.status != Booking.STATUS_CONFIRMED:
        raise Http404()

    return render(request, 'bookings/receipt.html', {
        'booking': booking,
        'cancellation_policy': CANCELLATION_POLICY,
    })


def view_receipt_pdf(request, booking_id, token):
    """
    Renders the booking receipt as a downloadable PDF via WeasyPrint.

    Uses the same access-control check as view_receipt (staff bypass or valid token).
    Returns the PDF as an attachment so browsers download it directly.

    NOTE: WeasyPrint requires native system libraries (Pango/Cairo) on the server.
    On Ubuntu: apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
    On Windows local dev: install the GTK3 runtime from WeasyPrint's Windows docs.
    """
    booking = get_object_or_404(Booking, id=booking_id)

    if not _check_receipt_access(request, booking, token):
        raise Http404()

    if booking.status != Booking.STATUS_CONFIRMED:
        raise Http404()

    # Render the HTML receipt template to a string
    html_string = render_to_string('bookings/receipt.html', {
        'booking': booking,
        'cancellation_policy': CANCELLATION_POLICY,
        # WeasyPrint needs an absolute base_url to resolve static file paths
        # (fonts, images). We pass the request's base URL for this.
        'request': request,
        'is_pdf': True,
    }, request=request)

    # Convert HTML to PDF bytes via WeasyPrint
    from weasyprint import HTML
    pdf_bytes = HTML(string=html_string,
                     base_url=request.build_absolute_uri('/')).write_pdf()

    reference = f"CH-{booking.id:05d}"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Coral-Heights-Receipt-{reference}.pdf"'
    return response


def booking_page(request):
    """
    Dedicated booking page view. Replaces the former modal flow so guests
    can complete OTP verification, hold room, and mock payment on a secure,
    dedicated page without risk of losing progress on accidental outside clicks.
    """
    room_type_slug = request.GET.get('room_type', '').strip()
    check_in_str = request.GET.get('check_in', '').strip()
    check_out_str = request.GET.get('check_out', '').strip()

    adults_raw = request.GET.get('adults')
    children_raw = request.GET.get('children')
    invalid_occupancy_input = False

    if adults_raw is not None:
        try:
            adults = int(adults_raw)
            if adults < 1:
                invalid_occupancy_input = True
                adults = 1
        except (ValueError, TypeError):
            invalid_occupancy_input = True
            adults = 2
    else:
        adults = 2

    if children_raw is not None:
        try:
            children = int(children_raw)
            if children < 0:
                invalid_occupancy_input = True
                children = 0
        except (ValueError, TypeError):
            invalid_occupancy_input = True
            children = 0
    else:
        children = 0

    all_room_types = RoomType.objects.prefetch_related('rooms').all()
    selected_room = None
    has_valid_selection = False
    is_available = False
    available_count = 0
    nights = 1
    price_per_night = 0.0
    total_amount = 0.0
    error_message = None

    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    if room_type_slug and check_in_str and check_out_str:
        try:
            check_in = parse_date_input(check_in_str)
            check_out = parse_date_input(check_out_str)
            # Normalize internal strings to ISO format for data attributes / API compatibility
            check_in_str = check_in.strftime('%Y-%m-%d')
            check_out_str = check_out.strftime('%Y-%m-%d')

            if check_in < today:
                error_message = "Check-in date cannot be in the past."
            elif check_out <= check_in:
                error_message = "Check-out date must be after check-in date."
            else:
                try:
                    selected_room = RoomType.objects.get(slug=room_type_slug)
                    nights = (check_out - check_in).days
                    available_count = get_available_rooms_count(selected_room, check_in, check_out)
                    is_available = available_count > 0
                    price_per_night = float(selected_room.base_price_per_night)
                    total_amount = price_per_night * nights

                    if invalid_occupancy_input:
                        error_message = "Invalid guest count provided."
                        has_valid_selection = False
                    elif (adults + children) > selected_room.max_occupancy:
                        error_message = f"Selected guests ({adults + children}) exceed maximum capacity of {selected_room.max_occupancy} for {selected_room.name}."
                        has_valid_selection = False
                    elif not is_available:
                        has_valid_selection = True
                        error_message = f"{selected_room.name} is fully booked for your selected dates."
                    else:
                        has_valid_selection = True
                except RoomType.DoesNotExist:
                    error_message = "The selected room type does not exist."
        except ValueError:
            error_message = "Invalid date format. Please use DD-MM-YYYY or YYYY-MM-DD."
    else:
        if room_type_slug:
            selected_room = RoomType.objects.filter(slug=room_type_slug).first()
        if not selected_room and all_room_types.exists():
            selected_room = all_room_types.first()
        if not check_in_str:
            check_in_str = today.strftime('%Y-%m-%d')
        if not check_out_str:
            check_out_str = tomorrow.strftime('%Y-%m-%d')

        if selected_room:
            if invalid_occupancy_input:
                error_message = "Invalid guest count provided."
            elif (adults + children) > selected_room.max_occupancy:
                error_message = f"Selected guests ({adults + children}) exceed maximum capacity of {selected_room.max_occupancy} for {selected_room.name}."

    check_in_display = format_date_dmy(check_in_str)
    check_out_display = format_date_dmy(check_out_str)

    context = {
        'room_types': all_room_types,
        'selected_room': selected_room,
        'check_in': check_in_str,
        'check_out': check_out_str,
        'check_in_display': check_in_display,
        'check_out_display': check_out_display,
        'adults': adults,
        'children': children,
        'nights': nights,
        'price_per_night': f"{price_per_night:.2f}",
        'total_amount': f"{total_amount:.2f}",
        'available_count': available_count,
        'is_available': is_available,
        'has_valid_selection': has_valid_selection,
        'error_message': error_message,
        'today': today.strftime('%Y-%m-%d'),
        'tomorrow': tomorrow.strftime('%Y-%m-%d'),
        'cancellation_policy': CANCELLATION_POLICY,
    }
    return render(request, 'bookings/booking_page.html', context)

