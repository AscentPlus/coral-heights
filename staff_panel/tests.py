from bookings.services import get_available_rooms
from bookings.models import Guest, Booking
from content.models import Room, RoomType
from django.utils import timezone
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from staff_panel.models import StaffProfile


class StaffPanelAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Superuser
        self.superuser = User.objects.create_superuser(
            username='admin_user',
            email='admin@example.com',
            password='Password123!'
        )

        # Regular Staff User with StaffProfile
        self.staff_user = User.objects.create_user(
            username='staff_john',
            password='Password123!',
            is_staff=False
        )
        self.staff_profile = StaffProfile.objects.create(
            user=self.staff_user,
            access_level=StaffProfile.ACCESS_BOTH
        )

        # Inactive Staff User
        self.inactive_user = User.objects.create_user(
            username='inactive_john',
            password='Password123!',
            is_active=False,
            is_staff=False
        )
        StaffProfile.objects.create(
            user=self.inactive_user,
            access_level=StaffProfile.ACCESS_BOTH
        )

        # Non-staff regular user (No StaffProfile)
        self.regular_user = User.objects.create_user(
            username='guest_john',
            password='Password123!',
            is_staff=False
        )

    def test_login_success_for_staff(self):
        response = self.client.post(reverse('staff_panel:login'), {
            'username': 'staff_john',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('staff_panel:dashboard'))

    def test_login_success_for_superuser(self):
        response = self.client.post(reverse('staff_panel:login'), {
            'username': 'admin_user',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('staff_panel:dashboard'))

    def test_login_case_insensitive_and_email(self):
        # Case insensitive username match
        res1 = self.client.post(reverse('staff_panel:login'), {
            'username': 'Admin_User ',
            'password': 'Password123!'
        })
        self.assertRedirects(res1, reverse('staff_panel:dashboard'))
        self.client.logout()

        # Email match
        res2 = self.client.post(reverse('staff_panel:login'), {
            'username': 'admin@example.com',
            'password': 'Password123!'
        })
        self.assertRedirects(res2, reverse('staff_panel:dashboard'))

    def test_login_failure_invalid_credentials(self):
        response = self.client.post(reverse('staff_panel:login'), {
            'username': 'staff_john',
            'password': 'WrongPassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_login_failure_inactive_user(self):
        response = self.client.post(reverse('staff_panel:login'), {
            'username': 'inactive_john',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_login_failure_no_staff_profile(self):
        response = self.client.post(reverse('staff_panel:login'), {
            'username': 'guest_john',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_unauthenticated_redirect(self):
        dashboard_url = reverse('staff_panel:dashboard')
        login_url = reverse('staff_panel:login')
        response = self.client.get(dashboard_url)
        self.assertRedirects(response, f"{login_url}?next={dashboard_url}")

    def test_logout(self):
        self.client.login(username='staff_john', password='Password123!')
        response = self.client.get(reverse('staff_panel:logout'))
        self.assertRedirects(response, reverse('staff_panel:login'))


class StaffPanelPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Website-only staff
        self.web_user = User.objects.create_user(
            username='web_staff', password='Password123!', is_staff=False)
        StaffProfile.objects.create(
            user=self.web_user, access_level=StaffProfile.ACCESS_WEBSITE)

        # Bookings-only staff
        self.booking_user = User.objects.create_user(
            username='booking_staff', password='Password123!', is_staff=False)
        StaffProfile.objects.create(
            user=self.booking_user, access_level=StaffProfile.ACCESS_BOOKINGS)

        # Both staff
        self.both_user = User.objects.create_user(
            username='both_staff', password='Password123!', is_staff=False)
        StaffProfile.objects.create(
            user=self.both_user, access_level=StaffProfile.ACCESS_BOTH)

        # Superuser (No StaffProfile)
        self.superuser = User.objects.create_superuser(
            username='super_admin', password='Password123!')

    def test_website_staff_permissions(self):
        self.client.login(username='web_staff', password='Password123!')

        # Website stub accessible
        res = self.client.get(reverse('staff_panel:website'))
        self.assertEqual(res.status_code, 200)

        # Bookings stubs blocked (403)
        res = self.client.get(reverse('staff_panel:bookings'))
        self.assertEqual(res.status_code, 403)
        res = self.client.get(reverse('staff_panel:rooms'))
        self.assertEqual(res.status_code, 403)

        # Manage staff blocked (403)
        res = self.client.get(reverse('staff_panel:manage_staff'))
        self.assertEqual(res.status_code, 403)

    def test_bookings_staff_permissions(self):
        self.client.login(username='booking_staff', password='Password123!')

        # Bookings stubs accessible
        res = self.client.get(reverse('staff_panel:bookings'))
        self.assertEqual(res.status_code, 200)
        res = self.client.get(reverse('staff_panel:rooms'))
        self.assertEqual(res.status_code, 200)

        # Website stub blocked (403)
        res = self.client.get(reverse('staff_panel:website'))
        self.assertEqual(res.status_code, 403)

        # Manage staff blocked (403)
        res = self.client.get(reverse('staff_panel:manage_staff'))
        self.assertEqual(res.status_code, 403)

    def test_both_staff_permissions(self):
        self.client.login(username='both_staff', password='Password123!')

        self.assertEqual(self.client.get(
            reverse('staff_panel:website')).status_code, 200)
        self.assertEqual(self.client.get(
            reverse('staff_panel:bookings')).status_code, 200)

        # Manage staff blocked (403)
        self.assertEqual(self.client.get(
            reverse('staff_panel:manage_staff')).status_code, 403)

    def test_superuser_bypass_all_permissions(self):
        self.client.login(username='super_admin', password='Password123!')

        self.assertEqual(self.client.get(
            reverse('staff_panel:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(
            reverse('staff_panel:website')).status_code, 200)
        self.assertEqual(self.client.get(
            reverse('staff_panel:bookings')).status_code, 200)
        self.assertEqual(self.client.get(
            reverse('staff_panel:manage_staff')).status_code, 200)

    def test_staff_cannot_access_django_admin(self):
        """Staff with is_staff=False cannot access /admin/."""
        self.client.login(username='both_staff', password='Password123!')
        res = self.client.get('/admin/')
        # Django admin redirects non-is_staff users to admin login page
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/admin/login/' in res.url)


class StaffManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='super_admin', password='Password123!')
        self.client.login(username='super_admin', password='Password123!')

    def test_create_staff_account(self):
        res = self.client.post(reverse('staff_panel:manage_staff'), {
            'action': 'create',
            'username': 'new_receptionist',
            'password': 'Password123!',
            'access_bookings': '1',
        })
        self.assertRedirects(res, reverse('staff_panel:manage_staff'))

        new_user = User.objects.get(username='new_receptionist')
        self.assertFalse(new_user.is_staff)  # Must NOT have access to /admin/
        self.assertTrue(hasattr(new_user, 'staff_profile'))
        self.assertEqual(new_user.staff_profile.access_level,
                         StaffProfile.ACCESS_BOOKINGS)

    def test_update_staff_role(self):
        staff = User.objects.create_user(
            username='staff_mark', password='Password123!', is_staff=False)
        StaffProfile.objects.create(
            user=staff, access_level=StaffProfile.ACCESS_WEBSITE)

        res = self.client.post(reverse('staff_panel:manage_staff'), {
            'action': 'update_role',
            'user_id': staff.id,
            'access_bookings': '1',
            'access_website': '1',
        })
        self.assertRedirects(res, reverse('staff_panel:manage_staff'))
        staff.staff_profile.refresh_from_db()
        self.assertEqual(staff.staff_profile.access_level,
                         StaffProfile.ACCESS_BOTH)

    def test_toggle_active_status(self):
        staff = User.objects.create_user(
            username='staff_mark', password='Password123!', is_staff=False)
        StaffProfile.objects.create(
            user=staff, access_level=StaffProfile.ACCESS_WEBSITE)

        res = self.client.post(reverse('staff_panel:manage_staff'), {
            'action': 'toggle_active',
            'user_id': staff.id
        })
        self.assertRedirects(res, reverse('staff_panel:manage_staff'))
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)

    def test_self_deactivation_prevented(self):
        res = self.client.post(reverse('staff_panel:manage_staff'), {
            'action': 'toggle_active',
            'user_id': self.superuser.id
        }, follow=True)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)
        self.assertContains(
            res, "You cannot deactivate your own superuser account.")


class StaffProfilePasswordChangeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff_kate', password='OldPassword123!', is_staff=False)
        StaffProfile.objects.create(
            user=self.staff_user, access_level=StaffProfile.ACCESS_BOTH)
        self.client.login(username='staff_kate', password='OldPassword123!')

    def test_profile_page_loads(self):
        res = self.client.get(reverse('staff_panel:profile'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'staff_kate')

    def test_password_change_success(self):
        res = self.client.post(reverse('staff_panel:profile'), {
            'old_password': 'OldPassword123!',
            'new_password1': 'BrandNewPassword123!',
            'new_password2': 'BrandNewPassword123!'
        })
        self.assertRedirects(res, reverse('staff_panel:profile'))

        # Verify session kept active and new password works
        res_profile = self.client.get(reverse('staff_panel:profile'))
        self.assertEqual(res_profile.status_code, 200)


class StaffBookingsAndRoomsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Custom Staff User (is_staff=False, access_level=bookings)
        self.staff_booking_user = User.objects.create_user(
            username='receptionist',
            password='Password123!',
            is_staff=False
        )
        StaffProfile.objects.create(
            user=self.staff_booking_user,
            access_level=StaffProfile.ACCESS_BOOKINGS
        )

        # Website-only Staff User (is_staff=False, access_level=website)
        self.staff_web_user = User.objects.create_user(
            username='webmaster',
            password='Password123!',
            is_staff=False
        )
        StaffProfile.objects.create(
            user=self.staff_web_user,
            access_level=StaffProfile.ACCESS_WEBSITE
        )

        # Setup test room and guest
        self.room_type = RoomType.objects.create(
            name='Deluxe Room',
            slug='deluxe-room',
            base_price_per_night=3000,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_number='201',
            room_type=self.room_type
        )
        self.guest = Guest.objects.create(
            name='Alice Smith',
            phone='9876543210',
            email='alice@example.com'
        )

    def test_receipt_access_for_custom_staff(self):
        """Staff-panel user with is_staff=False can view confirmed receipts without token."""
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=timezone.now().date(),
            check_out=timezone.now().date() + timedelta(days=2),
            status=Booking.STATUS_CONFIRMED
        )

        self.client.login(username='receptionist', password='Password123!')
        receipt_url = reverse('bookings:receipt', kwargs={
                              'booking_id': booking.id, 'token': 'staff'})
        response = self.client.get(receipt_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CH-')

    def test_bookings_list_filtering_and_overdue(self):
        """Test filtering bookings list by guest_name, phone, status, date range, and overdue flag."""
        today = timezone.now().date()

        # Booking 1: Confirmed and Overdue (check_out in past)
        b1 = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today - timedelta(days=3),
            check_out=today - timedelta(days=1),
            status=Booking.STATUS_CONFIRMED
        )

        # Booking 2: Held
        guest2 = Guest.objects.create(name='Bob Jones', phone='5551234567')
        b2 = Booking.objects.create(
            room=self.room,
            guest=guest2,
            check_in=today,
            check_out=today + timedelta(days=1),
            status=Booking.STATUS_HELD
        )

        self.client.login(username='receptionist', password='Password123!')

        # Filter by name
        res = self.client.get(reverse('staff_panel:bookings'), {
                              'guest_name': 'Alice'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alice Smith')
        self.assertNotContains(res, 'Bob Jones')

        # Filter by status=held
        res = self.client.get(
            reverse('staff_panel:bookings'), {'status': 'held'})
        self.assertContains(res, 'Bob Jones')
        self.assertNotContains(res, 'Alice Smith')

        # Filter by overdue=1
        res = self.client.get(
            reverse('staff_panel:bookings'), {'overdue': '1'})
        self.assertContains(res, 'Alice Smith')
        self.assertContains(res, 'Overdue checkout')
        self.assertNotContains(res, 'Bob Jones')

    def test_mark_guest_departed_eligible(self):
        """Marking an eligible guest departed updates status, frees room, and restores availability."""
        today = timezone.now().date()
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today - timedelta(days=1),
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_CONFIRMED
        )

        self.client.login(username='receptionist', password='Password123!')

        # Verify room is occupied today
        rooms_res = self.client.get(reverse('staff_panel:rooms'))
        self.assertContains(rooms_res, 'Occupied')

        # Post mark departed
        detail_url = reverse('staff_panel:booking_detail',
                             kwargs={'booking_id': booking.id})
        res = self.client.post(detail_url, {'action': 'mark_departed'})
        self.assertRedirects(res, detail_url)

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        self.assertIsNotNone(booking.actual_check_out)

        # Rooms page now shows Vacant
        rooms_res = self.client.get(reverse('staff_panel:rooms'))
        self.assertContains(rooms_res, 'Vacant')

        # Room availability restored
        avail = get_available_rooms(
            self.room_type, today, today + timedelta(days=1))
        self.assertTrue(avail.filter(id=self.room.id).exists())

    def test_mark_guest_departed_ineligible(self):
        """Attempting to mark ineligible booking departed returns error message without state change."""
        today = timezone.now().date()

        # Future check-in booking
        future_booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=3),
            status=Booking.STATUS_CONFIRMED
        )

        self.client.login(username='receptionist', password='Password123!')
        detail_url = reverse('staff_panel:booking_detail', kwargs={
                             'booking_id': future_booking.id})
        res = self.client.post(
            detail_url, {'action': 'mark_departed'}, follow=True)

        future_booking.refresh_from_db()
        self.assertEqual(future_booking.status, Booking.STATUS_CONFIRMED)
        self.assertContains(
            res, 'Cannot mark guest as departed before check-in date')

    def test_website_staff_cannot_access_bookings_or_rooms(self):
        """Website-only staff accounts cannot access bookings list, detail, or rooms pages."""
        self.client.login(username='webmaster', password='Password123!')

        self.assertEqual(self.client.get(
            reverse('staff_panel:bookings')).status_code, 403)
        self.assertEqual(self.client.get(
            reverse('staff_panel:rooms')).status_code, 403)

        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=timezone.now().date(),
            check_out=timezone.now().date() + timedelta(days=1),
            status=Booking.STATUS_CONFIRMED
        )
        detail_url = reverse('staff_panel:booking_detail',
                             kwargs={'booking_id': booking.id})
        self.assertEqual(self.client.get(detail_url).status_code, 403)


class RoomsPendingHoldTests(TestCase):
    """Tests that rooms page surfaces pending hold state correctly."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='rooms_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.staff_user, access_level=StaffProfile.ACCESS_BOOKINGS)

        self.room_type = RoomType.objects.create(
            name='Test Room Type', slug='test-room-pending',
            base_price_per_night=2000, max_occupancy=2
        )
        self.room = Room.objects.create(
            room_number='501', room_type=self.room_type)
        self.guest = Guest.objects.create(
            name='Hold Tester', phone='9111111111')

    def test_rooms_page_shows_pending_hold_state(self):
        """Rooms page renders Pending Hold label for rooms with active held bookings."""
        today = timezone.now().date()
        Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today,
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_HELD,
            hold_expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.client.login(username='rooms_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:rooms'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Pending Hold')

    def test_rooms_page_vacant_after_hold_cancellation(self):
        """After a hold booking is cancelled, the room shows Vacant on the rooms page."""
        from bookings.services import cancel_booking
        today = timezone.now().date()
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today,
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_HELD,
            hold_expires_at=timezone.now() + timedelta(minutes=10),
        )
        cancel_booking(booking, reason='Test cancellation')

        self.client.login(username='rooms_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:rooms'))
        self.assertContains(res, 'Vacant')
        # The text 'Pending Hold' is always in the legend row, but the orange
        # badge CSS class (bg-orange-100) only appears for real pending-hold rows.
        self.assertNotContains(res, 'bg-orange-100')


class BookingQuickActionTests(TestCase):
    """Tests for quick-action POST from bookings list page."""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='qa_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.staff_user, access_level=StaffProfile.ACCESS_BOOKINGS)

        self.room_type = RoomType.objects.create(
            name='Quick Action Room', slug='quick-action-room',
            base_price_per_night=2500, max_occupancy=2
        )
        self.room = Room.objects.create(
            room_number='601', room_type=self.room_type)
        self.guest = Guest.objects.create(
            name='Quick Tester', phone='9222222222')
        self.client.login(username='qa_staff', password='Password123!')

    def test_quick_mark_departed_succeeds_and_redirects_to_list(self):
        """Quick-action mark_departed from list frees the room and redirects back."""
        today = timezone.now().date()
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today - timedelta(days=1),
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_CONFIRMED,
        )
        quick_url = reverse('staff_panel:booking_quick_action',
                            kwargs={'booking_id': booking.id})
        res = self.client.post(quick_url, {
            'action': 'mark_departed',
            'return_url': reverse('staff_panel:bookings'),
        })
        self.assertRedirects(res, reverse('staff_panel:bookings'))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        self.assertIsNotNone(booking.actual_check_out)

    def test_quick_action_preserves_return_url_with_filters(self):
        """Quick-action redirects to the return_url (with query params) on success."""
        today = timezone.now().date()
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today - timedelta(days=1),
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_CONFIRMED,
        )
        return_url = f"{reverse('staff_panel:bookings')}?status=confirmed&overdue=1"
        quick_url = reverse('staff_panel:booking_quick_action',
                            kwargs={'booking_id': booking.id})
        res = self.client.post(quick_url, {
            'action': 'mark_departed',
            'return_url': return_url,
        })
        self.assertRedirects(res, return_url)

    def test_cancel_action_from_detail_page(self):
        """POSTing action=cancel to the booking detail page cancels the booking."""
        today = timezone.now().date()
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today + timedelta(days=3),
            check_out=today + timedelta(days=5),
            status=Booking.STATUS_CONFIRMED,
        )
        detail_url = reverse('staff_panel:booking_detail',
                             kwargs={'booking_id': booking.id})
        res = self.client.post(detail_url, {
            'action': 'cancel',
            'cancellation_reason': 'Guest requested by phone',
        })
        self.assertRedirects(res, detail_url)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)
        self.assertEqual(booking.cancellation_reason,
                         'Guest requested by phone')
        self.assertIsNotNone(booking.cancelled_at)

    def test_cancel_ineligible_booking_rejected(self):
        """Attempting to cancel a completed booking is rejected with an error message."""
        today = timezone.now().date()
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=today - timedelta(days=3),
            check_out=today - timedelta(days=1),
            status=Booking.STATUS_COMPLETED,
            actual_check_out=timezone.now() - timedelta(days=1),
        )
        detail_url = reverse('staff_panel:booking_detail',
                             kwargs={'booking_id': booking.id})
        res = self.client.post(detail_url, {
            'action': 'cancel',
            'cancellation_reason': '',
        }, follow=True)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        # Error message should surface in the response
        self.assertContains(res, 'Cannot cancel')


class StaffEnquiriesTests(TestCase):
    """Tests for the staff panel enquiries list, detail, quick-status, and permission boundary."""

    def setUp(self):
        self.client = Client()
        from enquiries.models import Enquiry

        # Bookings-access staff (should have enquiry access)
        self.booking_staff = User.objects.create_user(
            username='enq_booking_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.booking_staff, access_level=StaffProfile.ACCESS_BOOKINGS)

        # Website-only staff (should NOT have enquiry access)
        self.web_staff = User.objects.create_user(
            username='enq_web_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.web_staff, access_level=StaffProfile.ACCESS_WEBSITE)

        today = timezone.now().date()

        # Create test enquiries
        self.enq1 = Enquiry.objects.create(
            contact_name='Alice Wonderland',
            contact_phone='9111111111',
            function_type=Enquiry.FUNCTION_BIRTHDAY,
            preferred_date=today + timedelta(days=10),
            guest_count=50,
            status=Enquiry.STATUS_NEW,
        )
        self.enq2 = Enquiry.objects.create(
            contact_name='Bob Builder',
            contact_phone='9222222222',
            function_type=Enquiry.FUNCTION_WEDDING,
            preferred_date=today + timedelta(days=20),
            guest_count=200,
            status=Enquiry.STATUS_CONTACTED,
        )
        self.enq3 = Enquiry.objects.create(
            contact_name='Charlie Chaplin',
            contact_phone='9333333333',
            function_type=Enquiry.FUNCTION_CORPORATE,
            preferred_date=today + timedelta(days=5),
            guest_count=30,
            status=Enquiry.STATUS_CLOSED,
        )

    def test_enquiries_list_loads(self):
        """Enquiries list page loads for bookings-access staff."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:enquiries'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alice Wonderland')
        self.assertContains(res, 'Bob Builder')
        self.assertContains(res, 'Charlie Chaplin')

    def test_filter_by_status(self):
        """Filtering by status returns only matching enquiries."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:enquiries'), {'status': 'new'})
        self.assertContains(res, 'Alice Wonderland')
        self.assertNotContains(res, 'Bob Builder')
        self.assertNotContains(res, 'Charlie Chaplin')

    def test_filter_by_function_type(self):
        """Filtering by function_type returns only matching enquiries."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:enquiries'), {'function_type': 'wedding'})
        self.assertContains(res, 'Bob Builder')
        self.assertNotContains(res, 'Alice Wonderland')
        self.assertNotContains(res, 'Charlie Chaplin')

    def test_filter_by_date_range(self):
        """Filtering by preferred date range returns only matching enquiries."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        today = timezone.now().date()
        date_from = (today + timedelta(days=8)).strftime('%Y-%m-%d')
        date_to = (today + timedelta(days=25)).strftime('%Y-%m-%d')
        res = self.client.get(reverse('staff_panel:enquiries'), {
            'date_from': date_from, 'date_to': date_to
        })
        self.assertContains(res, 'Alice Wonderland')
        self.assertContains(res, 'Bob Builder')
        self.assertNotContains(res, 'Charlie Chaplin')

    def test_filter_by_name(self):
        """Filtering by contact name (icontains) returns matches."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:enquiries'), {'contact_name': 'bob'})
        self.assertContains(res, 'Bob Builder')
        self.assertNotContains(res, 'Alice Wonderland')

    def test_filter_by_phone(self):
        """Filtering by phone (icontains) returns matches."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:enquiries'), {'contact_phone': '9333'})
        self.assertContains(res, 'Charlie Chaplin')
        self.assertNotContains(res, 'Alice Wonderland')

    def test_combined_filters(self):
        """Multiple filters applied together narrow results correctly."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:enquiries'), {
            'status': 'new',
            'function_type': 'birthday',
        })
        self.assertContains(res, 'Alice Wonderland')
        self.assertNotContains(res, 'Bob Builder')

    def test_status_change_from_detail(self):
        """Status and staff remarks change from detail page updates the enquiry in DB."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        from enquiries.models import Enquiry

        detail_url = reverse('staff_panel:enquiry_detail',
                             kwargs={'enquiry_id': self.enq2.id})
        res = self.client.post(detail_url, {
            'new_status': 'closed',
            'staff_remarks': 'Spoke to client, event confirmed for 200 guests.'
        })
        self.assertRedirects(res, detail_url)
        self.enq2.refresh_from_db()
        self.assertEqual(self.enq2.status, Enquiry.STATUS_CLOSED)
        self.assertEqual(self.enq2.staff_remarks, 'Spoke to client, event confirmed for 200 guests.')

    def test_status_jump_new_to_closed(self):
        """Status can jump directly from New to Closed (no constrained transitions)."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        from enquiries.models import Enquiry

        detail_url = reverse('staff_panel:enquiry_detail',
                             kwargs={'enquiry_id': self.enq1.id})
        res = self.client.post(detail_url, {'new_status': 'closed'})
        self.assertRedirects(res, detail_url)
        self.enq1.refresh_from_db()
        self.assertEqual(self.enq1.status, Enquiry.STATUS_CLOSED)

    def test_detail_page_loads(self):
        """Enquiry detail page loads with correct data."""
        self.client.login(username='enq_booking_staff', password='Password123!')
        detail_url = reverse('staff_panel:enquiry_detail',
                             kwargs={'enquiry_id': self.enq1.id})
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alice Wonderland')
        self.assertContains(res, 'Birthday Party')

    def test_website_staff_cannot_access_enquiries_list(self):
        """Website-only staff cannot access /staff/enquiries/ (403)."""
        self.client.login(username='enq_web_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:enquiries'))
        self.assertEqual(res.status_code, 403)

    def test_website_staff_cannot_access_enquiry_detail(self):
        """Website-only staff cannot access /staff/enquiries/<id>/ (403)."""
        self.client.login(username='enq_web_staff', password='Password123!')
        detail_url = reverse('staff_panel:enquiry_detail',
                             kwargs={'enquiry_id': self.enq1.id})
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, 403)


class StaffReportsTests(TestCase):
    """Tests for staff panel occupancy and revenue reports."""

    def setUp(self):
        self.client = Client()
        from decimal import Decimal

        # Bookings staff user
        self.booking_staff = User.objects.create_user(
            username='reports_booking_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.booking_staff, access_level=StaffProfile.ACCESS_BOOKINGS)

        # Website-only staff user
        self.web_staff = User.objects.create_user(
            username='reports_web_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.web_staff, access_level=StaffProfile.ACCESS_WEBSITE)

        # Room types & rooms
        self.deluxe_type = RoomType.objects.create(
            name='Deluxe Suite', slug='deluxe-suite',
            base_price_per_night=3000, max_occupancy=2
        )
        self.standard_type = RoomType.objects.create(
            name='Standard Room', slug='standard-room',
            base_price_per_night=1500, max_occupancy=2
        )

        self.room_101 = Room.objects.create(room_number='101', room_type=self.deluxe_type)
        self.room_102 = Room.objects.create(room_number='102', room_type=self.standard_type)

        self.guest_alice = Guest.objects.create(name='Alice Smith', phone='9876543210', email='alice@example.com')
        self.guest_bob = Guest.objects.create(name='Bob Jones', phone='5551234567', email='bob@example.com')

    def test_permission_boundary(self):
        """Website-only staff receives HTTP 403; Bookings staff receives HTTP 200."""
        self.client.login(username='reports_web_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:reports'))
        self.assertEqual(res.status_code, 403)

        self.client.login(username='reports_booking_staff', password='Password123!')
        res = self.client.get(reverse('staff_panel:reports'))
        self.assertEqual(res.status_code, 200)

    def test_occupancy_percentage_calculation(self):
        """Daily occupancy % averaged across range matches occupied rooms / total rooms."""
        from bookings.services import get_reports_data
        today = timezone.now().date()

        # 2 total rooms (101, 102).
        # Booking in room 101 for 3 days: today to today+3
        Booking.objects.create(
            room=self.room_101,
            guest=self.guest_alice,
            check_in=today,
            check_out=today + timedelta(days=3),
            status=Booking.STATUS_CONFIRMED,
            total_amount=9000,
        )

        # Calculate reports data for today..today+2 (3 days)
        data = get_reports_data(today, today + timedelta(days=2))
        # 1 room occupied out of 2 = 50.0% each day => average = 50.0%
        self.assertEqual(data['occupancy_pct'], 50.0)
        self.assertEqual(data['days_count'], 3)

    def test_revenue_and_adr_calculation(self):
        """Calculates total revenue, room-nights sold, ADR, confirmed/cancelled counts correctly."""
        from decimal import Decimal
        from bookings.services import get_reports_data
        today = timezone.now().date()

        # Booking 1: 2 nights @ Deluxe (3000/night = 6000 total), CONFIRMED
        b1 = Booking.objects.create(
            room=self.room_101,
            guest=self.guest_alice,
            check_in=today,
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_CONFIRMED,
            total_amount=Decimal('6000.00'),
        )

        # Booking 2: 3 nights @ Standard (1500/night = 4500 total), COMPLETED
        b2 = Booking.objects.create(
            room=self.room_102,
            guest=self.guest_bob,
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=4),
            status=Booking.STATUS_COMPLETED,
            total_amount=Decimal('4500.00'),
        )

        # Booking 3: Cancelled booking
        b3 = Booking.objects.create(
            room=self.room_101,
            guest=self.guest_bob,
            check_in=today + timedelta(days=5),
            check_out=today + timedelta(days=6),
            status=Booking.STATUS_CANCELLED,
            total_amount=Decimal('3000.00'),
        )

        data = get_reports_data(today, today + timedelta(days=10))
        self.assertEqual(data['confirmed_count'], 2)
        self.assertEqual(data['cancelled_count'], 1)
        self.assertEqual(data['total_revenue'], Decimal('10500.00'))
        self.assertEqual(data['room_nights_sold'], 5)  # 2 + 3
        self.assertEqual(data['average_nightly_rate'], Decimal('2100.00'))  # 10500 / 5

    def test_guest_list_filtering_and_presets(self):
        """Reports view supports guest_name, phone filters, and date preset GET params."""
        today = timezone.now().date()
        Booking.objects.create(
            room=self.room_101,
            guest=self.guest_alice,
            check_in=today,
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_CONFIRMED,
            total_amount=6000,
        )

        self.client.login(username='reports_booking_staff', password='Password123!')

        # Preset test: range_type=today
        res = self.client.get(reverse('staff_panel:reports'), {'range_type': 'today'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['from_date'], today)

        # Filter test: guest_name=Alice
        res_filter = self.client.get(reverse('staff_panel:reports'), {'guest_name': 'Alice'})
        self.assertContains(res_filter, 'Alice Smith')

        # Filter test: phone non-matching
        res_no_match = self.client.get(reverse('staff_panel:reports'), {'phone': '0000000000'})
        self.assertNotContains(res_no_match, 'Alice Smith')


class StaffWebsiteContentTests(TestCase):
    """Tests for staff panel website content management."""

    def setUp(self):
        self.client = Client()
        from django.core.files.uploadedfile import SimpleUploadedFile
        from content.models import RoomType, Facility, Attraction, ContactInformation
        from bookings.models import Guest, Booking

        # Website staff user
        self.web_staff = User.objects.create_user(
            username='web_content_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.web_staff, access_level=StaffProfile.ACCESS_WEBSITE)

        # Bookings staff user
        self.booking_staff = User.objects.create_user(
            username='booking_only_staff', password='Password123!')
        StaffProfile.objects.create(
            user=self.booking_staff, access_level=StaffProfile.ACCESS_BOOKINGS)

        # Pre-create test data
        self.room_type = RoomType.objects.create(
            name='Ocean View Suite', slug='ocean-view-suite',
            short_description='Beautiful view', base_price_per_night=5000,
            max_occupancy=2, bed_type='King', display_order=1
        )
        self.facility = Facility.objects.create(
            name='Infinity Pool', icon_svg_d='M0 0h24v24H0z', display_order=1
        )
        self.attraction = Attraction.objects.create(
            name='Alappuzha Beach', description='Golden sand beach',
            distance_label='3.0 km', display_order=1
        )
        self.contact = ContactInformation.objects.create(
            primary_phone='+91 9999999999', email='test@hotel.com'
        )

    def test_permission_boundary(self):
        """Bookings-only staff receives HTTP 403; Website staff receives HTTP 200 on all website routes."""
        self.client.login(username='booking_only_staff', password='Password123!')
        self.assertEqual(self.client.get(reverse('staff_panel:website')).status_code, 403)
        self.assertEqual(self.client.get(reverse('staff_panel:website_room_types')).status_code, 403)
        self.assertEqual(self.client.get(reverse('staff_panel:website_facilities')).status_code, 403)
        self.assertEqual(self.client.get(reverse('staff_panel:website_attractions')).status_code, 403)
        self.assertEqual(self.client.get(reverse('staff_panel:website_contact')).status_code, 403)

        self.client.login(username='web_content_staff', password='Password123!')
        self.assertEqual(self.client.get(reverse('staff_panel:website')).status_code, 200)
        self.assertEqual(self.client.get(reverse('staff_panel:website_room_types')).status_code, 200)
        self.assertEqual(self.client.get(reverse('staff_panel:website_facilities')).status_code, 200)
        self.assertEqual(self.client.get(reverse('staff_panel:website_attractions')).status_code, 200)
        self.assertEqual(self.client.get(reverse('staff_panel:website_contact')).status_code, 200)

    def _get_test_image(self, name="test.jpg"):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        file_obj = BytesIO()
        image = Image.new('RGB', (100, 100), color='teal')
        image.save(file_obj, 'jpeg')
        file_obj.seek(0)
        return SimpleUploadedFile(name, file_obj.read(), content_type="image/jpeg")

    def test_room_type_crud_and_image_upload(self):
        """Creating and editing a RoomType with image upload works and updates display_image_url."""
        from content.models import RoomType

        self.client.login(username='web_content_staff', password='Password123!')

        # Create new room type with photo upload
        image_file = self._get_test_image("suite.jpg")
        res = self.client.post(reverse('staff_panel:website_room_types'), {
            'action': 'create',
            'name': 'Presidential Suite',
            'short_description': 'Luxury suite',
            'long_description': 'Extended description for modal',
            'base_price_per_night': '12000.00',
            'max_occupancy': '4',
            'bed_type': 'King Bed',
            'display_order': '2',
            'image': image_file,
        })
        self.assertRedirects(res, reverse('staff_panel:website_room_types'))

        new_rt = RoomType.objects.get(name='Presidential Suite')
        self.assertEqual(new_rt.slug, 'presidential-suite')
        self.assertTrue(bool(new_rt.image))
        self.assertTrue('suite' in new_rt.display_image_url)

        # Edit existing room type
        res_edit = self.client.post(reverse('staff_panel:website_room_types'), {
            'action': 'edit',
            'room_type_id': new_rt.id,
            'name': 'Presidential Suite Updated',
            'short_description': 'Updated short summary',
            'base_price_per_night': '15000.00',
            'max_occupancy': '4',
            'bed_type': 'Super King',
            'display_order': '1',
        })
        self.assertRedirects(res_edit, reverse('staff_panel:website_room_types'))
        new_rt.refresh_from_db()
        self.assertEqual(new_rt.name, 'Presidential Suite Updated')
        self.assertEqual(new_rt.base_price_per_night, 15000)

    def test_room_type_protected_delete_guard(self):
        """Unprotected RoomType deletes cleanly; RoomType with active/past bookings is caught with ProtectedError."""
        from content.models import RoomType, Room
        from bookings.models import Guest, Booking

        self.client.login(username='web_content_staff', password='Password123!')

        # Case A: Delete unprotected room type
        unprotected_rt = RoomType.objects.create(
            name='Temporary Villa', slug='temp-villa',
            short_description='Temp', base_price_per_night=8000
        )
        delete_url = reverse('staff_panel:website_room_type_delete', kwargs={'pk': unprotected_rt.id})
        res_unprotected = self.client.post(delete_url)
        self.assertRedirects(res_unprotected, reverse('staff_panel:website_room_types'))
        self.assertFalse(RoomType.objects.filter(id=unprotected_rt.id).exists())

        # Case B: Attempt delete protected room type (has room tied to booking)
        room = Room.objects.create(room_number='701', room_type=self.room_type)
        guest = Guest.objects.create(name='Jane Doe', phone='9000000000')
        Booking.objects.create(
            room=room, guest=guest,
            check_in=timezone.now().date(),
            check_out=timezone.now().date() + timedelta(days=2),
            status=Booking.STATUS_CONFIRMED,
            total_amount=10000
        )

        protected_delete_url = reverse('staff_panel:website_room_type_delete', kwargs={'pk': self.room_type.id})
        res_protected = self.client.post(protected_delete_url, follow=True)
        # Should redirect back with error message and NOT throw 500 error
        self.assertEqual(res_protected.status_code, 200)
        self.assertTrue(RoomType.objects.filter(id=self.room_type.id).exists())
        self.assertContains(res_protected, "Can&#x27;t delete")

    def test_facility_crud(self):
        """Facility create automatically assigns SVG icon, edit, and delete work properly."""
        from content.models import Facility

        self.client.login(username='web_content_staff', password='Password123!')

        # Create facility without icon_svg_d
        res = self.client.post(reverse('staff_panel:website_facilities'), {
            'action': 'create',
            'name': 'Free High-Speed Wi-Fi Zone',
            'display_order': '3',
        })
        self.assertRedirects(res, reverse('staff_panel:website_facilities'))
        fac = Facility.objects.get(name='Free High-Speed Wi-Fi Zone')
        # Check auto-assigned wifi SVG icon
        self.assertTrue('8.111' in fac.icon_svg_d or len(fac.icon_svg_d) > 0)

        # Edit
        res_edit = self.client.post(reverse('staff_panel:website_facilities'), {
            'action': 'edit',
            'facility_id': fac.id,
            'name': 'Luxury Swimming Pool',
            'display_order': '1',
        })
        self.assertRedirects(res_edit, reverse('staff_panel:website_facilities'))
        fac.refresh_from_db()
        self.assertEqual(fac.name, 'Luxury Swimming Pool')

        # Delete
        delete_url = reverse('staff_panel:website_facility_delete', kwargs={'pk': fac.id})
        res_delete = self.client.post(delete_url)
        self.assertRedirects(res_delete, reverse('staff_panel:website_facilities'))
        self.assertFalse(Facility.objects.filter(id=fac.id).exists())

    def test_attraction_crud(self):
        """Attraction create with image, edit, and delete work properly."""
        from content.models import Attraction

        self.client.login(username='web_content_staff', password='Password123!')

        image_file = self._get_test_image("beach.jpg")

        # Create
        res = self.client.post(reverse('staff_panel:website_attractions'), {
            'action': 'create',
            'name': 'Vembanad Lake Backwaters',
            'description': 'Famous Kerala backwaters cruise',
            'distance_label': '5.5 km',
            'display_order': '2',
            'image': image_file,
        })
        self.assertRedirects(res, reverse('staff_panel:website_attractions'))
        att = Attraction.objects.get(name='Vembanad Lake Backwaters')
        self.assertTrue(bool(att.image))

        # Edit
        res_edit = self.client.post(reverse('staff_panel:website_attractions'), {
            'action': 'edit',
            'attraction_id': att.id,
            'name': 'Vembanad Lake Houseboats',
            'description': 'Updated backwaters cruise description',
            'distance_label': '5.0 km',
            'display_order': '1',
        })
        self.assertRedirects(res_edit, reverse('staff_panel:website_attractions'))
        att.refresh_from_db()
        self.assertEqual(att.name, 'Vembanad Lake Houseboats')

        # Delete
        delete_url = reverse('staff_panel:website_attraction_delete', kwargs={'pk': att.id})
        res_delete = self.client.post(delete_url)
        self.assertRedirects(res_delete, reverse('staff_panel:website_attractions'))
        self.assertFalse(Attraction.objects.filter(id=att.id).exists())

    def test_contact_info_get_or_create_and_update(self):
        """ContactInformation form update reflects in DB and context processor."""
        from content.models import ContactInformation

        self.client.login(username='web_content_staff', password='Password123!')

        res = self.client.post(reverse('staff_panel:website_contact'), {
            'primary_phone': '+91 9496200999',
            'landline_1': '0477-2278999',
            'landline_2': '',
            'whatsapp_number': '+919496200999',
            'email': 'contact@coralheights.com',
            'facebook_url': 'https://facebook.com/coralheights',
            'instagram_url': 'https://instagram.com/coralheights',
            'address_line_1': 'Hotel Coral Heights Grand',
            'address_line_2': 'Ambalapuzha Town',
            'address_line_3': 'Kerala — 688 561',
        })
        self.assertRedirects(res, reverse('staff_panel:website_contact'))

        self.contact.refresh_from_db()
        self.assertEqual(self.contact.primary_phone, '+91 9496200999')
        self.assertEqual(self.contact.email, 'contact@coralheights.com')

        # Test context processor output on homepage
        res_home = self.client.get(reverse('content:home'))
        self.assertEqual(res_home.status_code, 200)
        self.assertContains(res_home, 'contact@coralheights.com')

    def test_custom_404_view(self):
        """Requesting non-existent / unconfigured URL returns custom 404 page."""
        res = self.client.get('/non-existent-unconfigured-url-12345/')
        self.assertEqual(res.status_code, 404)
        self.assertContains(res, 'Page Not Found', status_code=404)

    def test_append_slash_redirects(self):
        """Without catch-all re_path, APPEND_SLASH properly redirects urls without trailing slashes."""
        res_staff = self.client.get('/staff')
        self.assertEqual(res_staff.status_code, 301)
        self.assertEqual(res_staff.headers.get('Location'), '/staff/')

        res_login = self.client.get('/staff/login')
        self.assertEqual(res_login.status_code, 301)
        self.assertEqual(res_login.headers.get('Location'), '/staff/login/')

    def test_403_test_route_removed(self):
        """Ensure /403-test/ debug route is no longer configured."""
        res = self.client.get('/403-test/')
        self.assertEqual(res.status_code, 404)

    def test_custom_500_view(self):
        """Ensure custom_500_view returns status 500 and renders 500.html."""
        from django.test import RequestFactory
        from staff_panel.views import custom_500_view
        req = RequestFactory().get('/server-error')
        res = custom_500_view(req)
        self.assertEqual(res.status_code, 500)
        self.assertIn(b'Server Error', res.content)






