from bookings.services import (
    mark_booking_departed, cancel_booking, expire_stale_holds,
    get_overdue_bookings, get_room_statuses_today, get_reports_data
)
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone
from django.db.models import Q, ProtectedError

from content.models import Room, RoomType, Facility, Attraction, ContactInformation
from bookings.models import Booking
from enquiries.models import Enquiry

from .models import StaffProfile
from .forms import (
    StaffLoginForm, StaffCreateForm,
    RoomTypeForm, FacilityForm, AttractionForm, ContactInformationForm
)
from .permissions import (
    has_panel_access,
    has_website_access,
    has_bookings_access,
    staff_login_required,
    website_access_required,
    bookings_access_required,
    superuser_required
)


def staff_login(request):
    if request.user.is_authenticated and has_panel_access(request.user):
        next_url = request.GET.get('next') or reverse('staff_panel:dashboard')
        return redirect(next_url)

    error_message = None
    form = StaffLoginForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            username_input = form.cleaned_data['username'].strip()
            password_input = form.cleaned_data['password'].strip()

            user = authenticate(
                request, username=username_input, password=password_input)

            if user is None:
                # Try finding user by case-insensitive username or email
                matched_user = User.objects.filter(
                    Q(username__iexact=username_input) | Q(
                        email__iexact=username_input)
                ).first()
                if matched_user:
                    user = authenticate(
                        request, username=matched_user.username, password=password_input)

            if user is not None and user.is_active and has_panel_access(user):
                login(request, user)
                next_url = request.GET.get('next') or reverse(
                    'staff_panel:dashboard')
                return redirect(next_url)
            else:
                error_message = "Invalid username or password."
        else:
            error_message = "Invalid username or password."

    return render(request, 'staff_panel/login.html', {
        'form': form,
        'error_message': error_message
    })


def staff_logout(request):
    logout(request)
    return redirect('staff_panel:login')


@staff_login_required
def dashboard(request):
    today = timezone.now().date()
    context = {
        'today': today,
    }

    if has_bookings_access(request.user):
        context['total_rooms'] = Room.objects.count()
        room_statuses = get_room_statuses_today()
        context['occupied_rooms'] = sum(
            1 for r in room_statuses if r['is_occupied'])
        context['overdue_count'] = get_overdue_bookings().count()
        context['bookings_today'] = Booking.objects.filter(
            created_at__date=today).count()
        context['pending_enquiries'] = Enquiry.objects.filter(
            status=Enquiry.STATUS_NEW).count()

    if has_website_access(request.user):
        context['room_types_count'] = RoomType.objects.count()

    return render(request, 'staff_panel/dashboard.html', context)


@bookings_access_required
def bookings_list(request):
    # Opportunistic cleanup: cancel genuinely expired holds before rendering.
    # Keeps the list tidy between scheduler runs (cheap — indexed query).
    expire_stale_holds()

    bookings_qs = Booking.objects.select_related(
        'guest', 'room', 'room__room_type').all()

    guest_name = request.GET.get('guest_name', '').strip()
    phone = request.GET.get('phone', '').strip()
    status = request.GET.get('status', '').strip()
    check_in_from = request.GET.get('check_in_from', '').strip()
    check_in_to = request.GET.get('check_in_to', '').strip()
    overdue = request.GET.get('overdue', '').strip()

    if guest_name:
        bookings_qs = bookings_qs.filter(guest__name__icontains=guest_name)
    if phone:
        bookings_qs = bookings_qs.filter(guest__phone__icontains=phone)
    if status:
        bookings_qs = bookings_qs.filter(status=status)
    if check_in_from:
        try:
            from_date = datetime.strptime(check_in_from, '%Y-%m-%d').date()
            bookings_qs = bookings_qs.filter(check_in__gte=from_date)
        except ValueError:
            pass
    if check_in_to:
        try:
            to_date = datetime.strptime(check_in_to, '%Y-%m-%d').date()
            bookings_qs = bookings_qs.filter(check_in__lte=to_date)
        except ValueError:
            pass
    if overdue == '1':
        today = timezone.now().date()
        bookings_qs = bookings_qs.filter(
            status=Booking.STATUS_CONFIRMED,
            check_out__lt=today,
            actual_check_out__isnull=True
        )

    paginator = Paginator(bookings_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'staff_panel/bookings_list.html', {
        'page_obj': page_obj,
        'guest_name': guest_name,
        'phone': phone,
        'status': status,
        'check_in_from': check_in_from,
        'check_in_to': check_in_to,
        'overdue': overdue,
        'status_choices': Booking.STATUS_CHOICES,
        'today': timezone.now().date(),
    })


@bookings_access_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related(
        'guest', 'room', 'room__room_type'), id=booking_id)
    today = timezone.now().date()
    is_eligible_for_departure = (
        booking.status == Booking.STATUS_CONFIRMED and booking.check_in <= today)
    is_eligible_for_cancellation = booking.status in (
        Booking.STATUS_HELD, Booking.STATUS_CONFIRMED)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_departed':
            success, msg = mark_booking_departed(booking)
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('staff_panel:booking_detail', booking_id=booking.id)

        elif action == 'cancel':
            reason = request.POST.get('cancellation_reason', '').strip()
            success, msg = cancel_booking(booking, reason=reason)
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('staff_panel:booking_detail', booking_id=booking.id)

    receipt_url = None
    if booking.status == Booking.STATUS_CONFIRMED:
        receipt_url = reverse('bookings:receipt', kwargs={
                              'booking_id': booking.id, 'token': booking.access_token})

    return render(request, 'staff_panel/booking_detail.html', {
        'booking': booking,
        'is_eligible_for_departure': is_eligible_for_departure,
        'is_eligible_for_cancellation': is_eligible_for_cancellation,
        'receipt_url': receipt_url,
    })


@bookings_access_required
def booking_quick_action(request, booking_id):
    """
    Handles quick-action POSTs from the bookings list (mark_departed).
    Redirects back to the list, preserving all active filter parameters.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('guest', 'room'), id=booking_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_departed':
            success, msg = mark_booking_departed(booking)
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)

    # Preserve filter query params when redirecting back to the list
    return_url = request.POST.get('return_url', '')
    if return_url and return_url.startswith('/staff/'):
        return redirect(return_url)
    return redirect('staff_panel:bookings')


@bookings_access_required
def rooms_list(request):
    room_statuses = get_room_statuses_today()
    return render(request, 'staff_panel/rooms_list.html', {
        'room_statuses': room_statuses,
        'today': timezone.now().date(),
    })


@bookings_access_required
def enquiries_list(request):
    enquiries_qs = Enquiry.objects.all()

    contact_name = request.GET.get('contact_name', '').strip()
    contact_phone = request.GET.get('contact_phone', '').strip()
    status = request.GET.get('status', '').strip()
    function_type = request.GET.get('function_type', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if contact_name:
        enquiries_qs = enquiries_qs.filter(contact_name__icontains=contact_name)
    if contact_phone:
        enquiries_qs = enquiries_qs.filter(contact_phone__icontains=contact_phone)
    if status:
        enquiries_qs = enquiries_qs.filter(status=status)
    if function_type:
        enquiries_qs = enquiries_qs.filter(function_type=function_type)
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            enquiries_qs = enquiries_qs.filter(preferred_date__gte=from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            enquiries_qs = enquiries_qs.filter(preferred_date__lte=to_date)
        except ValueError:
            pass

    paginator = Paginator(enquiries_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'staff_panel/enquiries_list.html', {
        'page_obj': page_obj,
        'contact_name': contact_name,
        'contact_phone': contact_phone,
        'status': status,
        'function_type': function_type,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Enquiry.STATUS_CHOICES,
        'function_choices': Enquiry.FUNCTION_CHOICES,
    })


@bookings_access_required
def enquiry_detail(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, id=enquiry_id)

    if request.method == 'POST':
        new_status = request.POST.get('new_status', '').strip()
        staff_remarks = request.POST.get('staff_remarks', '').strip()

        valid_statuses = [s[0] for s in Enquiry.STATUS_CHOICES]
        if new_status in valid_statuses:
            enquiry.status = new_status
            enquiry.staff_remarks = staff_remarks
            enquiry.save()
            messages.success(
                request, "Enquiry details updated successfully.")
        else:
            messages.error(request, "Invalid status selected.")
        return redirect('staff_panel:enquiry_detail', enquiry_id=enquiry.id)

    return render(request, 'staff_panel/enquiry_detail.html', {
        'enquiry': enquiry,
        'status_choices': Enquiry.STATUS_CHOICES,
    })



@bookings_access_required
def reports_view(request):
    today = timezone.now().date()

    range_type = request.GET.get('range_type', '').strip()
    from_str = request.GET.get('from', '').strip()
    to_str = request.GET.get('to', '').strip()
    guest_name = request.GET.get('guest_name', '').strip()
    phone = request.GET.get('phone', '').strip()

    # Determine date range
    if range_type == 'today':
        from_date = today
        to_date = today
    elif range_type == 'this_week':
        from_date = today - timedelta(days=today.weekday())
        to_date = from_date + timedelta(days=6)
    elif range_type == 'last_month':
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        from_date = last_of_last_month.replace(day=1)
        to_date = last_of_last_month
    elif range_type == 'this_month':
        from_date = today.replace(day=1)
        next_month = (from_date + timedelta(days=32)).replace(day=1)
        to_date = next_month - timedelta(days=1)
    else:
        if from_str and to_str:
            try:
                from_date = datetime.strptime(from_str, '%Y-%m-%d').date()
                to_date = datetime.strptime(to_str, '%Y-%m-%d').date()
                if to_date < from_date:
                    to_date = from_date
            except ValueError:
                from_date = today.replace(day=1)
                next_month = (from_date + timedelta(days=32)).replace(day=1)
                to_date = next_month - timedelta(days=1)
        else:
            range_type = 'this_month'
            from_date = today.replace(day=1)
            next_month = (from_date + timedelta(days=32)).replace(day=1)
            to_date = next_month - timedelta(days=1)

    reports_data = get_reports_data(
        from_date=from_date,
        to_date=to_date,
        guest_name=guest_name,
        phone=phone
    )

    # Paginate guest list
    guest_list_qs = reports_data['guest_list_qs']
    paginator = Paginator(guest_list_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Preset date strings for quick links
    this_month_start = today.replace(day=1)
    next_month = (this_month_start + timedelta(days=32)).replace(day=1)
    this_month_end = next_month - timedelta(days=1)

    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    this_week_start = today - timedelta(days=today.weekday())
    this_week_end = this_week_start + timedelta(days=6)

    context = {
        'from_date': from_date,
        'to_date': to_date,
        'from_str': from_date.strftime('%Y-%m-%d'),
        'to_str': to_date.strftime('%Y-%m-%d'),
        'guest_name': guest_name,
        'phone': phone,
        'range_type': range_type,
        'today': today,
        'confirmed_count': reports_data['confirmed_count'],
        'cancelled_count': reports_data['cancelled_count'],
        'total_revenue': reports_data['total_revenue'],
        'room_nights_sold': reports_data['room_nights_sold'],
        'average_nightly_rate': reports_data['average_nightly_rate'],
        'occupancy_pct': reports_data['occupancy_pct'],
        'days_count': reports_data['days_count'],
        'room_type_breakdown': reports_data['room_type_breakdown'],
        'page_obj': page_obj,
        'preset_today_from': today.strftime('%Y-%m-%d'),
        'preset_today_to': today.strftime('%Y-%m-%d'),
        'preset_week_from': this_week_start.strftime('%Y-%m-%d'),
        'preset_week_to': this_week_end.strftime('%Y-%m-%d'),
        'preset_month_from': this_month_start.strftime('%Y-%m-%d'),
        'preset_month_to': this_month_end.strftime('%Y-%m-%d'),
        'preset_last_month_from': last_month_start.strftime('%Y-%m-%d'),
        'preset_last_month_to': last_month_end.strftime('%Y-%m-%d'),
    }

    return render(request, 'staff_panel/reports.html', context)


@website_access_required
def website_dashboard(request):
    contact, _ = ContactInformation.objects.get_or_create()
    context = {
        'room_types_count': RoomType.objects.count(),
        'facilities_count': Facility.objects.count(),
        'attractions_count': Attraction.objects.count(),
        'contact': contact,
    }
    return render(request, 'staff_panel/website/dashboard.html', context)


@website_access_required
def website_room_types(request):
    room_types = RoomType.objects.all()
    form = RoomTypeForm()
    edit_id = request.GET.get('edit')
    edit_room_type = None

    if edit_id:
        edit_room_type = get_object_or_404(RoomType, id=edit_id)
        if request.method != 'POST':
            form = RoomTypeForm(instance=edit_room_type)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            form = RoomTypeForm(request.POST, request.FILES)
            if form.is_valid():
                rt = form.save()
                messages.success(request, f"Room type '{rt.name}' created successfully.")
                return redirect('staff_panel:website_room_types')
            else:
                messages.error(request, "Failed to create room type. Please check errors below.")
        elif action == 'edit':
            rt_id = request.POST.get('room_type_id')
            edit_room_type = get_object_or_404(RoomType, id=rt_id)
            form = RoomTypeForm(request.POST, request.FILES, instance=edit_room_type)
            if form.is_valid():
                form.save()
                messages.success(request, f"Room type '{edit_room_type.name}' updated successfully.")
                return redirect('staff_panel:website_room_types')
            else:
                messages.error(request, "Failed to update room type. Please check errors below.")

    return render(request, 'staff_panel/website/room_types.html', {
        'room_types': room_types,
        'form': form,
        'edit_room_type': edit_room_type,
    })


@website_access_required
def website_room_type_delete(request, pk):
    if request.method == 'POST':
        room_type = get_object_or_404(RoomType, pk=pk)
        try:
            name = room_type.name
            room_type.delete()
            messages.success(request, f"Room type '{name}' deleted successfully.")
        except ProtectedError:
            messages.error(request, f"Can't delete '{room_type.name}' — this room type has booking history.")
    return redirect('staff_panel:website_room_types')


@website_access_required
def website_facilities(request):
    facilities = Facility.objects.all()
    form = FacilityForm()
    edit_id = request.GET.get('edit')
    edit_facility = None

    if edit_id:
        edit_facility = get_object_or_404(Facility, id=edit_id)
        if request.method != 'POST':
            form = FacilityForm(instance=edit_facility)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            form = FacilityForm(request.POST)
            if form.is_valid():
                fac = form.save()
                messages.success(request, f"Facility '{fac.name}' added successfully.")
                return redirect('staff_panel:website_facilities')
            else:
                messages.error(request, "Failed to add facility. Please check errors below.")
        elif action == 'edit':
            fac_id = request.POST.get('facility_id')
            edit_facility = get_object_or_404(Facility, id=fac_id)
            form = FacilityForm(request.POST, instance=edit_facility)
            if form.is_valid():
                form.save()
                messages.success(request, f"Facility '{edit_facility.name}' updated successfully.")
                return redirect('staff_panel:website_facilities')
            else:
                messages.error(request, "Failed to update facility. Please check errors below.")

    return render(request, 'staff_panel/website/facilities.html', {
        'facilities': facilities,
        'form': form,
        'edit_facility': edit_facility,
    })


@website_access_required
def website_facility_delete(request, pk):
    if request.method == 'POST':
        facility = get_object_or_404(Facility, pk=pk)
        name = facility.name
        facility.delete()
        messages.success(request, f"Facility '{name}' deleted successfully.")
    return redirect('staff_panel:website_facilities')


@website_access_required
def website_attractions(request):
    attractions = Attraction.objects.all()
    form = AttractionForm()
    edit_id = request.GET.get('edit')
    edit_attraction = None

    if edit_id:
        edit_attraction = get_object_or_404(Attraction, id=edit_id)
        if request.method != 'POST':
            form = AttractionForm(instance=edit_attraction)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            form = AttractionForm(request.POST, request.FILES)
            if form.is_valid():
                att = form.save()
                messages.success(request, f"Attraction '{att.name}' added successfully.")
                return redirect('staff_panel:website_attractions')
            else:
                messages.error(request, "Failed to add attraction. Please check errors below.")
        elif action == 'edit':
            att_id = request.POST.get('attraction_id')
            edit_attraction = get_object_or_404(Attraction, id=att_id)
            form = AttractionForm(request.POST, request.FILES, instance=edit_attraction)
            if form.is_valid():
                form.save()
                messages.success(request, f"Attraction '{edit_attraction.name}' updated successfully.")
                return redirect('staff_panel:website_attractions')
            else:
                messages.error(request, "Failed to update attraction. Please check errors below.")

    return render(request, 'staff_panel/website/attractions.html', {
        'attractions': attractions,
        'form': form,
        'edit_attraction': edit_attraction,
    })


@website_access_required
def website_attraction_delete(request, pk):
    if request.method == 'POST':
        attraction = get_object_or_404(Attraction, pk=pk)
        name = attraction.name
        attraction.delete()
        messages.success(request, f"Attraction '{name}' deleted successfully.")
    return redirect('staff_panel:website_attractions')


@website_access_required
def website_contact(request):
    contact, _ = ContactInformation.objects.get_or_create()
    if request.method == 'POST':
        form = ContactInformationForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact information & social settings updated successfully.")
            return redirect('staff_panel:website_contact')
        else:
            messages.error(request, "Failed to update contact settings. Please check errors below.")
    else:
        form = ContactInformationForm(instance=contact)

    return render(request, 'staff_panel/website/contact.html', {
        'form': form,
        'contact': contact,
    })



@superuser_required
def manage_staff(request):
    staff_users = User.objects.filter(is_superuser=False).select_related(
        'staff_profile').order_by('-date_joined')
    create_form = StaffCreateForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            create_form = StaffCreateForm(request.POST)
            if create_form.is_valid():
                new_user = create_form.save()
                messages.success(
                    request, f"Staff account '{new_user.username}' created successfully.")
                return redirect('staff_panel:manage_staff')

        elif action == 'update_role':
            user_id = request.POST.get('user_id')
            target_user = get_object_or_404(
                User, id=user_id, is_superuser=False)

            access_bookings = request.POST.get('access_bookings') == '1'
            access_website = request.POST.get('access_website') == '1'

            if access_bookings and access_website:
                access_level = StaffProfile.ACCESS_BOTH
            elif access_website:
                access_level = StaffProfile.ACCESS_WEBSITE
            elif access_bookings:
                access_level = StaffProfile.ACCESS_BOOKINGS
            else:
                messages.error(
                    request, f"Please select at least one section checkbox for '{target_user.username}'.")
                return redirect('staff_panel:manage_staff')

            if hasattr(target_user, 'staff_profile'):
                target_user.staff_profile.access_level = access_level
                target_user.staff_profile.save()
                messages.success(
                    request, f"Permissions for '{target_user.username}' updated.")
            return redirect('staff_panel:manage_staff')

        elif action == 'toggle_active':
            user_id = request.POST.get('user_id')
            target_user = get_object_or_404(User, id=user_id)

            if target_user.id == request.user.id or target_user.is_superuser:
                messages.warning(
                    request, "You cannot deactivate your own superuser account.")
            else:
                target_user.is_active = not target_user.is_active
                target_user.save()
                status_str = "activated" if target_user.is_active else "deactivated"
                messages.success(
                    request, f"Staff account '{target_user.username}' has been {status_str}.")
            return redirect('staff_panel:manage_staff')

    return render(request, 'staff_panel/manage_staff.html', {
        'staff_users': staff_users,
        'create_form': create_form,
        'access_choices': StaffProfile.ACCESS_CHOICES,
    })


@staff_login_required
def profile(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)
            messages.success(
                request, "Your password was changed successfully!")
            return redirect('staff_panel:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(user=request.user)

    user_role = "Superuser (Full Access)" if request.user.is_superuser else getattr(
        request.user.staff_profile, 'get_access_level_display', lambda: 'Staff')()

    return render(request, 'staff_panel/profile.html', {
        'form': form,
        'user_role': user_role
    })


def custom_404_view(request, exception=None, *args, **kwargs):
    return render(request, '404.html', status=404)


def custom_403_view(request, exception=None, *args, **kwargs):
    return render(request, '403.html', status=403)


def custom_500_view(request, *args, **kwargs):
    from django.template import loader
    from django.http import HttpResponseServerError
    template = loader.get_template('500.html')
    return HttpResponseServerError(template.render())


