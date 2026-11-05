from django.utils import timezone
from django.db.models import Q
from content.models import RoomType, Room
from .models import Booking


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
    Check-in date convention: all metrics and stay lists filter by check_in__range=(from_date, to_date).
    """
    from decimal import Decimal
    from datetime import timedelta
    from django.db.models import Sum

    days_count = (to_date - from_date).days + 1
    if days_count < 1:
        days_count = 1

    # Bookings with check_in falling in the date range
    range_bookings = Booking.objects.filter(
        check_in__range=(from_date, to_date)
    ).select_related('guest', 'room', 'room__room_type')

    # Confirmed & Completed bookings (valid revenue stays)
    valid_statuses = [Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED]
    confirmed_qs = range_bookings.filter(status__in=valid_statuses)
    cancelled_qs = range_bookings.filter(status=Booking.STATUS_CANCELLED)

    confirmed_count = confirmed_qs.count()
    cancelled_count = cancelled_qs.count()

    total_revenue = confirmed_qs.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

    # Total room-nights sold in range
    room_nights_sold = sum((b.check_out - b.check_in).days for b in confirmed_qs)

    # Average Nightly Rate (ADR)
    if room_nights_sold > 0:
        average_nightly_rate = total_revenue / Decimal(room_nights_sold)
    else:
        average_nightly_rate = Decimal('0.00')

    # Occupancy % calculation across each day in [from_date, to_date]
    total_rooms = Room.objects.count()
    daily_occupancies = []

    if total_rooms > 0:
        for i in range(days_count):
            curr_date = from_date + timedelta(days=i)
            occupied_count = Booking.objects.filter(
                status__in=valid_statuses,
                check_in__lte=curr_date,
                check_out__gt=curr_date
            ).values('room_id').distinct().count()

            daily_occ = (occupied_count / total_rooms) * 100.0
            daily_occupancies.append(daily_occ)

        occupancy_pct = sum(daily_occupancies) / float(days_count)
    else:
        occupancy_pct = 0.0

    # Room-Type breakdown
    room_types = RoomType.objects.all()
    room_type_breakdown = []

    for rt in room_types:
        rt_confirmed = confirmed_qs.filter(room__room_type=rt)
        rt_count = rt_confirmed.count()
        rt_rev = rt_confirmed.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        rt_nights = sum((b.check_out - b.check_in).days for b in rt_confirmed)
        rt_pct = float(rt_rev / total_revenue) * 100.0 if total_revenue > 0 else 0.0

        room_type_breakdown.append({
            'room_type': rt,
            'count': rt_count,
            'nights': rt_nights,
            'revenue': rt_rev,
            'revenue_pct': rt_pct,
        })

    # Guest stay list (filterable by guest_name and phone)
    guest_list_qs = range_bookings
    if guest_name:
        guest_list_qs = guest_list_qs.filter(guest__name__icontains=guest_name)
    if phone:
        guest_list_qs = guest_list_qs.filter(guest__phone__icontains=phone)

    return {
        'confirmed_count': confirmed_count,
        'cancelled_count': cancelled_count,
        'total_revenue': total_revenue,
        'room_nights_sold': room_nights_sold,
        'average_nightly_rate': average_nightly_rate,
        'occupancy_pct': round(occupancy_pct, 1),
        'days_count': days_count,
        'room_type_breakdown': room_type_breakdown,
        'guest_list_qs': guest_list_qs,
    }
