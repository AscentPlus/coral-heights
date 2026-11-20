from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
from datetime import timedelta
from content.models import RoomType, Room
from .models import Booking
from .constants import CANCELLATION_POLICY


def calculate_booking_pricing(room_type, check_in, check_out, adults=1, children=0):
    """
    Shared pricing and policy calculation across availability, booking, checkout, and receipt.
    Uses verified RoomType base price and standard hotel policies.
    """
    nights = (check_out - check_in).days
    if nights < 1:
        nights = 1
    price_per_night = room_type.base_price_per_night
    base_amount = price_per_night * Decimal(nights)
    tax_amount = Decimal('0.00')
    total_amount = base_amount + tax_amount
    return {
        'nights': nights,
        'price_per_night': price_per_night,
        'base_amount': base_amount,
        'tax_amount': tax_amount,
        'tax_note': 'Taxes included in published tariff',
        'total_amount': total_amount,
        'meal_plan': 'Room Only (EP)',
        'inclusions': [
            'Complimentary Wi-Fi',
            'Complimentary bottled water',
            'Free on-site parking',
        ],
        'cancellation_policy': CANCELLATION_POLICY,
    }



def get_available_rooms(room_type, check_in_date, check_out_date):
    """
    Returns a QuerySet of physical Room objects available for a given RoomType and date range.

    A room is unavailable if it has a booking that is:
    - status='confirmed', OR
    - status='held' with hold_expires_at in the future (> timezone.now())
    - AND date overlap: existing.check_in < requested_check_out AND existing.check_out > requested_check_in
    """
    if isinstance(room_type, str):
        try:
            room_type = RoomType.objects.get(slug=room_type)
        except RoomType.DoesNotExist:
            return Room.objects.none()

    now = timezone.now()

    # Blocking status condition
    status_filter = Q(status=Booking.STATUS_CONFIRMED) | (
        Q(status=Booking.STATUS_HELD) & Q(hold_expires_at__gt=now)
    )

    # Date overlap condition
    overlap_filter = Q(check_in__lt=check_out_date) & Q(
        check_out__gt=check_in_date)

    # Find distinct rooms of this room_type that have blocking overlapping bookings
    blocked_room_ids = Booking.objects.filter(
        room__room_type=room_type
    ).filter(
        status_filter
    ).filter(
        overlap_filter
    ).values_list('room_id', flat=True).distinct()

    return Room.objects.filter(room_type=room_type).exclude(id__in=blocked_room_ids)


def get_available_rooms_count(room_type, check_in_date, check_out_date):
    """
    Returns the number of available physical rooms for a given RoomType and date range.
    """
    return get_available_rooms(room_type, check_in_date, check_out_date).count()


def mark_booking_departed(booking):
    """
    Marks a guest as departed for a booking.
    Returns (success: bool, message: str).
    """
    if booking.status != Booking.STATUS_CONFIRMED:
        return False, "Only confirmed bookings can be marked as departed."

    today = timezone.now().date()
    if booking.check_in > today:
        return False, "Cannot mark guest as departed before check-in date."

    now = timezone.now()
    booking.status = Booking.STATUS_COMPLETED
    booking.actual_check_out = now
    booking.save()
    return True, f"Booking CH-{booking.id:05d} marked as departed and room freed."


def cancel_booking(booking, reason=''):
    """
    Cancels a held or confirmed booking.
    Returns (success: bool, message: str).

    NOTE: This only marks the booking cancelled in our system — it does NOT process
    any refund. Real payment/refund handling is a separate concern deferred until
    Razorpay actually goes live; the mock gateway has nothing to reverse.
    """
    if booking.status not in (Booking.STATUS_HELD, Booking.STATUS_CONFIRMED):
        return False, (
            f"Cannot cancel a booking with status '{booking.get_status_display()}'. "
            "Only held or confirmed bookings can be cancelled."
        )

    now = timezone.now()
    booking.status = Booking.STATUS_CANCELLED
    booking.cancelled_at = now
    booking.cancellation_reason = reason
    booking.save()
    return True, f"Booking CH-{booking.id:05d} has been cancelled."


def expire_stale_holds():
    """
    Finds all held bookings whose hold_expires_at is in the past and cancels them.
    Returns the count of bookings expired.

    Does not process any refunds — expired holds were never confirmed/paid.
    Intended to run periodically (cron/celery-beat) once deployed; also called
    opportunistically by the staff bookings-list view to keep the panel tidy.
    """
    now = timezone.now()
    stale_holds = Booking.objects.filter(
        status=Booking.STATUS_HELD,
        hold_expires_at__lt=now,
    )
    count = 0
    for booking in stale_holds:
        success, _ = cancel_booking(
            booking, reason='Hold expired — payment not completed')
        if success:
            count += 1
    return count


def get_overdue_bookings():
    """
    Returns QuerySet of confirmed bookings where check_out is in the past (< today)
    and actual_check_out is null.
    """
    today = timezone.now().date()
    return Booking.objects.filter(
        status=Booking.STATUS_CONFIRMED,
        check_out__lt=today,
        actual_check_out__isnull=True
    )


def get_room_statuses_today():
    """
    Returns a list of status dictionaries for all rooms today.
    Each dict includes:
      - room: Room instance
      - is_occupied: bool (confirmed booking in progress today)
      - booking: Booking | None (for occupied rooms)
      - is_overdue: bool
      - pending_hold: bool (active held booking for this room today)
      - hold_booking: Booking | None (the held booking, if pending_hold)
    """
    today = timezone.now().date()
    now = timezone.now()
    rooms = Room.objects.select_related('room_type').order_by('room_number')

    # Confirmed bookings active today
    active_bookings = Booking.objects.filter(
        status=Booking.STATUS_CONFIRMED,
        check_in__lte=today,
        actual_check_out__isnull=True
    ).select_related('guest', 'room', 'room__room_type')

    booking_map = {b.room_id: b for b in active_bookings}

    # Active held bookings for today (unexpired, dates overlap today)
    held_bookings = Booking.objects.filter(
        status=Booking.STATUS_HELD,
        hold_expires_at__gt=now,
        check_in__lte=today,
        check_out__gt=today,
    ).select_related('guest', 'room', 'room__room_type')

    hold_map = {b.room_id: b for b in held_bookings}

    result = []
    for room in rooms:
        booking = booking_map.get(room.id)
        hold_booking = hold_map.get(room.id)
        if booking:
            is_overdue = booking.check_out < today
            result.append({
                'room': room,
                'is_occupied': True,
                'booking': booking,
                'is_overdue': is_overdue,
                'pending_hold': False,
                'hold_booking': None,
            })
        elif hold_booking:
            result.append({
                'room': room,
                'is_occupied': False,
                'booking': None,
                'is_overdue': False,
                'pending_hold': True,
                'hold_booking': hold_booking,
            })
        else:
            result.append({
                'room': room,
                'is_occupied': False,
                'booking': None,
                'is_overdue': False,
                'pending_hold': False,
                'hold_booking': None,
            })
    return result


def get_reports_data(from_date, to_date, guest_name='', phone=''):
    """
    Calculates occupancy and revenue reports data for a given date range [from_date, to_date].
    Calculates occupancy and room-nights by overnight stay date for the selected period.
    Correctly accounts for stays crossing month-end and eliminates N+1 per-day queries.
    """
    days_count = (to_date - from_date).days + 1
    if days_count < 1:
        days_count = 1

    valid_statuses = [Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED]

    # Stays that overlap the selected period [from_date, to_date]
    # An overnight stay on date d requires check_in <= d and check_out > d.
    # Therefore, a booking has at least one overnight stay in [from_date, to_date] if:
    # check_in <= to_date and check_out > from_date
    overlapping_valid_bookings = list(Booking.objects.filter(
        status__in=valid_statuses,
        check_in__lte=to_date,
        check_out__gt=from_date
    ).select_related('guest', 'room', 'room__room_type'))

    # All bookings that arrived in the range (for cancellation tracking and check-in logs)
    arrival_bookings = Booking.objects.filter(
        check_in__range=(from_date, to_date)
    ).select_related('guest', 'room', 'room__room_type')

    cancelled_count = arrival_bookings.filter(status=Booking.STATUS_CANCELLED).count()
    confirmed_count = len(overlapping_valid_bookings)

    total_revenue = Decimal('0.00')
    room_nights_sold = 0

    # Build daily occupancy sets: index i corresponds to (from_date + i days)
    daily_occupied_rooms = [set() for _ in range(days_count)]
    rt_stats = {}  # rt_id -> {'room_type': rt, 'booking_ids': set(), 'nights': 0, 'revenue': Decimal('0.00')}

    for b in overlapping_valid_bookings:
        # Determine overlap with [from_date, to_date]
        stay_start = max(b.check_in, from_date)
        stay_end = min(b.check_out, to_date + timedelta(days=1))
        nights_in_period = (stay_end - stay_start).days

        if nights_in_period > 0:
            room_nights_sold += nights_in_period

            # Prorated or full revenue for nights falling strictly within this reporting period
            total_stay_nights = (b.check_out - b.check_in).days
            if total_stay_nights > 0 and b.total_amount:
                nightly_rate = b.total_amount / Decimal(total_stay_nights)
                period_revenue = nightly_rate * Decimal(nights_in_period)
            elif b.room and b.room.room_type:
                period_revenue = b.room.room_type.base_price_per_night * Decimal(nights_in_period)
            else:
                period_revenue = Decimal('0.00')
            total_revenue += period_revenue

            rt = b.room.room_type
            if rt.id not in rt_stats:
                rt_stats[rt.id] = {
                    'room_type': rt,
                    'booking_ids': set(),
                    'nights': 0,
                    'revenue': Decimal('0.00'),
                }
            rt_stats[rt.id]['booking_ids'].add(b.id)
            rt_stats[rt.id]['nights'] += nights_in_period
            rt_stats[rt.id]['revenue'] += period_revenue

            # Record room occupied for each night within the period
            for i in range(days_count):
                day_date = from_date + timedelta(days=i)
                if b.check_in <= day_date < b.check_out:
                    daily_occupied_rooms[i].add(b.room_id)

    if room_nights_sold > 0:
        average_nightly_rate = total_revenue / Decimal(room_nights_sold)
    else:
        average_nightly_rate = Decimal('0.00')

    total_rooms = Room.objects.count()
    if total_rooms > 0:
        daily_occupancy_pcts = [
            (len(occupied) / float(total_rooms)) * 100.0
            for occupied in daily_occupied_rooms
        ]
        occupancy_pct = sum(daily_occupancy_pcts) / float(days_count)
    else:
        occupancy_pct = 0.0

    # Room-Type breakdown
    room_types = RoomType.objects.all()
    room_type_breakdown = []
    for rt in room_types:
        st = rt_stats.get(rt.id, {
            'room_type': rt,
            'booking_ids': set(),
            'nights': 0,
            'revenue': Decimal('0.00')
        })
        rt_rev = st['revenue']
        rt_pct = float(rt_rev / total_revenue) * 100.0 if total_revenue > 0 else 0.0
        room_type_breakdown.append({
            'room_type': rt,
            'count': len(st['booking_ids']),
            'nights': st['nights'],
            'revenue': rt_rev,
            'revenue_pct': rt_pct,
        })

    # Guest stay list (filterable by guest_name and phone)
    guest_list_items = overlapping_valid_bookings
    if guest_name:
        guest_list_items = [b for b in guest_list_items if guest_name.lower() in (b.guest.name or '').lower()]
    if phone:
        guest_list_items = [b for b in guest_list_items if phone.lower() in (b.guest.phone or '').lower()]

    guest_list_items.sort(key=lambda b: b.check_in, reverse=True)

    return {
        'confirmed_count': confirmed_count,
        'cancelled_count': cancelled_count,
        'total_revenue': total_revenue,
        'room_nights_sold': room_nights_sold,
        'average_nightly_rate': average_nightly_rate,
        'occupancy_pct': round(occupancy_pct, 1),
        'days_count': days_count,
        'room_type_breakdown': room_type_breakdown,
        'guest_list_qs': guest_list_items,
    }
