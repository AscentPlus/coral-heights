from staff_panel.permissions import has_bookings_access
import json
import logging
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
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from content.models import RoomType, Room
from .models import Guest, Booking, PhoneOTP
from .services import (
    get_available_rooms,
    get_available_rooms_count,
    calculate_booking_pricing,
)
from .phone import canonicalize_phone, is_valid_phone
from .otp_gateway import get_otp_gateway
from .payment_gateway import get_payment_gateway
from .constants import CANCELLATION_POLICY

logger = logging.getLogger(__name__)


def parse_post_data(request):
    if request.content_type == 'application/json' and request.body:
        try:
            parsed = json.loads(request.body)
            if isinstance(parsed, dict):
                return parsed
            return {}
        except Exception:
            return {}
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

    today = timezone.localdate()
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

    stay_days = (check_out - check_in).days
    if stay_days > 30:
        return JsonResponse(
            {'error': 'Maximum stay limit is 30 days. For longer stays, please contact the hotel directly.'},
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
    adults = 1
    children = 0
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
    pricing = calculate_booking_pricing(room_type, check_in, check_out, adults, children)

    return JsonResponse({
        'available': available_count > 0,
        'count': available_count,
        'room_type_name': room_type.name,
        'price_per_night': f"{pricing['price_per_night']:.2f}",
        'nights': pricing['nights'],
        'total_amount': f"{pricing['total_amount']:.2f}",
        'cancellation_policy': pricing['cancellation_policy'],
    })


def get_client_ip(request):
    """
    Extract client IP from env-configured header (e.g., HTTP_CF_CONNECTING_IP, HTTP_X_FORWARDED_FOR)
    or fall back to REMOTE_ADDR. When parsing multi-hop headers like X-Forwarded-For,
    trust the last hop appended by the trusted reverse proxy rather than client-controlled first values.
    """
    header_name = getattr(settings, 'CLIENT_IP_HEADER', None)
    if getattr(settings, 'TRUST_FORWARDED_FOR', False) or header_name:
        header = header_name or 'HTTP_X_FORWARDED_FOR'
        raw_val = request.META.get(header, '').strip()
        if raw_val:
            hops = [h.strip() for h in raw_val.split(',') if h.strip()]
            if hops:
                return hops[-1]
    return request.META.get('REMOTE_ADDR', '127.0.0.1').strip()


def send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    data = parse_post_data(request)
    if not isinstance(data, dict):
        return JsonResponse({'success': False, 'error': 'Invalid request format.'}, status=400)

    raw_phone = str(data.get('phone') or '').strip()
    phone = canonicalize_phone(raw_phone)

    if not is_valid_phone(phone):
        return JsonResponse({'success': False, 'error': 'Please enter a valid phone number.'}, status=400)

    # Rate limiting: max 5 sends per IP per 10 minutes (600 seconds)
    client_ip = get_client_ip(request)
    ip_cache_key = f"otp_ratelimit_ip_{client_ip}" if client_ip else None
    if ip_cache_key:
        try:
            ip_count = cache.get(ip_cache_key)
            if ip_count is not None and ip_count >= 5:
                return JsonResponse({
                    'success': False,
                    'error': 'Too many verification code requests from this network. Please wait 10 minutes.'
                }, status=429)
        except Exception as e:
            logger.warning("Cache unavailable for OTP rate limit check: %s", e)

    now = timezone.now()

    # Rate limiting: check if non-expired OTP for this canonical phone was created < 30 seconds ago
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
        try:
            if cache.get(ip_cache_key) is None:
                cache.set(ip_cache_key, 1, timeout=600)
            else:
                try:
                    cache.incr(ip_cache_key)
                except ValueError:
                    cache.set(ip_cache_key, 1, timeout=600)
        except Exception as e:
            logger.warning("Cache unavailable for OTP rate limit update: %s", e)

    otp_gateway = get_otp_gateway()
    otp_gateway.send(phone, code)

    res_payload = {
        'success': True,
        'cooldown_seconds': 30
    }
    # Explicit demo flag: only return debug_otp when DEMO_SHOW_OTP is True (disabled in production)
    if getattr(settings, 'DEMO_SHOW_OTP', False):
        res_payload['debug_otp'] = code

    return JsonResponse(res_payload)


def verify_and_hold(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    data = parse_post_data(request)
    if not isinstance(data, dict):
        return JsonResponse({'success': False, 'error': 'Invalid request format.'}, status=400)

    raw_phone = str(data.get('phone') or '').strip()
    phone = canonicalize_phone(raw_phone)
    code = str(data.get('code') or '').strip()
    guest_name = str(data.get('guest_name') or '').strip()
    raw_email = str(data.get('guest_email') or '').strip()
    guest_email = raw_email if raw_email and raw_email.lower() not in ('null', 'none', 'undefined') else None
    room_type_slug = str(data.get('room_type') or '').strip()
    check_in_str = str(data.get('check_in') or '').strip()
    check_out_str = str(data.get('check_out') or '').strip()

    if not phone or not is_valid_phone(phone):
        return JsonResponse({'success': False, 'error': 'Please enter a valid phone number.'}, status=400)

    if not code:
        return JsonResponse({'success': False, 'error': 'Please enter the verification code.'}, status=400)

    if not guest_name:
        return JsonResponse({'success': False, 'error': 'Please enter the guest name.'}, status=400)

    if len(guest_name) > 100:
        return JsonResponse({'success': False, 'error': 'Guest name must be 100 characters or fewer.'}, status=400)

    if guest_email:
        try:
            validate_email(guest_email)
        except ValidationError:
            return JsonResponse({'success': False, 'error': 'Please enter a valid email address.'}, status=400)

    if not room_type_slug or not check_in_str or not check_out_str:
        return JsonResponse({'success': False, 'error': 'All booking fields must be provided.'}, status=400)

    try:
        raw_adults = data.get('adults', 1)
        adults = int(1 if raw_adults is None else raw_adults)
        raw_children = data.get('children', 0)
        children = int(0 if raw_children is None else raw_children)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Adults and children must be valid numbers.'}, status=400)

    if adults < 1:
        return JsonResponse({'success': False, 'error': 'Adults must be at least 1.'}, status=400)
    if children < 0:
        return JsonResponse({'success': False, 'error': 'Children cannot be negative.'}, status=400)

    # Validate dates
    try:
        check_in = parse_date_input(check_in_str)
        check_out = parse_date_input(check_out_str)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid date format. Please use DD-MM-YYYY or YYYY-MM-DD.'}, status=400)

    today = timezone.localdate()
    if check_in < today:
        return JsonResponse({'success': False, 'error': 'Check-in date cannot be in the past.'}, status=400)
    if check_out <= check_in:
        return JsonResponse({'success': False, 'error': 'Check-out date must be after check-in date.'}, status=400)

    stay_days = (check_out - check_in).days
    if stay_days > 30:
        return JsonResponse({'success': False, 'error': 'Maximum stay limit is 30 days.'}, status=400)

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

    now = timezone.now()

    # Atomic hold and OTP verification: lock PhoneOTP and candidate Room rows
    with transaction.atomic():
        # Atomically lock and retrieve unverified OTP row
        otp = PhoneOTP.objects.select_for_update().filter(
            phone=phone, is_verified=False
        ).order_by('-created_at').first()

        if not otp or otp.expires_at <= now:
            return JsonResponse({'success': False, 'error': 'OTP code has expired or is invalid. Please request a new code.'}, status=400)

        if otp.attempts >= 5:
            return JsonResponse({'success': False, 'error': 'Too many failed attempts. Please request a new code.'}, status=429)

        if otp.code != code:
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            remaining = max(0, 5 - otp.attempts)
            if remaining == 0:
                return JsonResponse({'success': False, 'error': 'Too many failed attempts. Please request a new code.'}, status=429)
            return JsonResponse({'success': False, 'error': f'Invalid code. {remaining} attempt{"s" if remaining > 1 else ""} remaining.'}, status=400)

        # Acquire row locks on candidate rooms to prevent race conditions
        list(Room.objects.select_for_update().filter(room_type=room_type))

        # Re-check availability right now against locked candidate rooms
        available_rooms = get_available_rooms(room_type, check_in, check_out)
        if not available_rooms.exists():
            # Room sold out! Crucially, do NOT set otp.is_verified=True, so guest can try other dates
            return JsonResponse(
                {'success': False, 'error': 'Sorry, this room type just sold out for these dates. Please search for alternative options.'},
                status=409
            )

        room = available_rooms.first()

        # Mark OTP verified atomically now that room hold is guaranteed
        otp.is_verified = True
        otp.save(update_fields=['is_verified'])

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

        pricing = calculate_booking_pricing(room_type, check_in, check_out, adults, children)
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
            total_amount=pricing['total_amount']
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
        'nights': pricing['nights'],
        'price_per_night': f"{pricing['price_per_night']:.2f}",
        'total_amount': f"{pricing['total_amount']:.2f}",
        'hold_expires_at': hold_expires_at.isoformat()
    })


def mock_pay(request, booking_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    # In production, strictly reject mock payment unless ALLOW_MOCK_PAYMENT is explicitly enabled
    if not getattr(settings, 'DEBUG', False) and not getattr(settings, 'ALLOW_MOCK_PAYMENT', False):
        return JsonResponse({
            'success': False,
            'error': 'Online payment is not enabled in production. Please contact reservations directly.'
        }, status=503)

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
    Access is granted if:
    - The user is authenticated staff with bookings-panel access, OR
    - The provided token matches the booking's access_token.
    """
    is_staff_viewer = request.user.is_authenticated and has_bookings_access(request.user)
    return is_staff_viewer or (token and token == booking.access_token)


def view_receipt(request, booking_id, token):
    booking = get_object_or_404(Booking, id=booking_id)

    if not _check_receipt_access(request, booking, token):
        raise Http404()

    if booking.status not in (Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED):
        raise Http404()

    response = render(request, 'bookings/receipt.html', {
        'booking': booking,
        'cancellation_policy': CANCELLATION_POLICY,
    })
    response['Cache-Control'] = 'private, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Referrer-Policy'] = 'no-referrer'
    return response


def view_receipt_pdf(request, booking_id, token):
    booking = get_object_or_404(Booking, id=booking_id)

    if not _check_receipt_access(request, booking, token):
        raise Http404()

    if booking.status not in (Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED):
        raise Http404()

    html_string = render_to_string('bookings/receipt.html', {
        'booking': booking,
        'cancellation_policy': CANCELLATION_POLICY,
        'request': request,
        'is_pdf': True,
    }, request=request)

    from weasyprint import HTML
    pdf_bytes = HTML(string=html_string,
                     base_url=request.build_absolute_uri('/')).write_pdf()

    reference = f"CH-{booking.id:05d}"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Coral-Heights-Receipt-{reference}.pdf"'
    response['Cache-Control'] = 'private, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Referrer-Policy'] = 'no-referrer'
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

    today = timezone.localdate()
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
            elif (check_out - check_in).days > 30:
                error_message = "Maximum stay limit is 30 days. For longer stays, please contact the hotel directly."
            else:
                try:
                    selected_room = RoomType.objects.get(slug=room_type_slug)
                    nights = (check_out - check_in).days
                    available_count = get_available_rooms_count(selected_room, check_in, check_out)
                    is_available = available_count > 0
                    pricing = calculate_booking_pricing(selected_room, check_in, check_out, adults, children)
                    price_per_night = float(pricing['price_per_night'])
                    total_amount = float(pricing['total_amount'])

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

    online_checkout_available = (
        getattr(settings, 'DEBUG', False)
        or getattr(settings, 'ALLOW_MOCK_PAYMENT', False)
        or getattr(settings, 'PAYMENT_GATEWAY', 'mock') != 'mock'
    )

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
        'online_checkout_available': online_checkout_available,
    }
    return render(request, 'bookings/booking_page.html', context)

