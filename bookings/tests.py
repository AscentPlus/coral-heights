from datetime import date, timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.cache import cache

from content.models import RoomType, Room
from bookings.models import Guest, Booking, PhoneOTP
from bookings.services import get_available_rooms_count


class AvailabilityTestCase(TestCase):
    def setUp(self):
        self.room_type = RoomType.objects.create(
            name="Deluxe Suite",
            slug="deluxe-suite",
            short_description="Spacious room",
            base_price_per_night=3500.00,
            max_occupancy=2
        )
        self.room1 = Room.objects.create(
            room_type=self.room_type, room_number="101")
        self.room2 = Room.objects.create(
            room_type=self.room_type, room_number="102")
        self.guest = Guest.objects.create(
            name="John Doe", phone="+919876543210")

    def test_no_bookings_fully_available(self):
        """When no bookings exist, total physical rooms should be available."""
        check_in = date.today() + timedelta(days=5)
        check_out = check_in + timedelta(days=2)
        count = get_available_rooms_count(self.room_type, check_in, check_out)
        self.assertEqual(count, 2)

    def test_exact_date_match_blocked(self):
        """Confirmed booking on exact date range blocks 1 room."""
        check_in = date.today() + timedelta(days=5)
        check_out = check_in + timedelta(days=2)

        Booking.objects.create(
            room=self.room1,
            guest=self.guest,
            check_in=check_in,
            check_out=check_out,
            status=Booking.STATUS_CONFIRMED
        )

        count = get_available_rooms_count(self.room_type, check_in, check_out)
        self.assertEqual(count, 1)

    def test_same_day_checkout_checkin_does_not_block(self):
        """Booking that ends on the check-in day of new booking does NOT block."""
        check_in = date.today() + timedelta(days=5)
        check_out = check_in + timedelta(days=2)

        # Existing booking checkout = new checkin
        Booking.objects.create(
            room=self.room1,
            guest=self.guest,
            check_in=check_in - timedelta(days=2),
            check_out=check_in,
            status=Booking.STATUS_CONFIRMED
        )

        count = get_available_rooms_count(self.room_type, check_in, check_out)
        self.assertEqual(count, 2)

    def test_expired_held_booking_does_not_block(self):
        """Held booking whose hold_expires_at is in the past does NOT block."""
        check_in = date.today() + timedelta(days=5)
        check_out = check_in + timedelta(days=2)

        Booking.objects.create(
            room=self.room1,
            guest=self.guest,
            check_in=check_in,
            check_out=check_out,
            status=Booking.STATUS_HELD,
            hold_expires_at=timezone.now() - timedelta(minutes=10)
        )

        count = get_available_rooms_count(self.room_type, check_in, check_out)
        self.assertEqual(count, 2)

    def test_active_held_booking_blocks(self):
        """Held booking whose hold_expires_at is in the future DOES block."""
        check_in = date.today() + timedelta(days=5)
        check_out = check_in + timedelta(days=2)

        Booking.objects.create(
            room=self.room1,
            guest=self.guest,
            check_in=check_in,
            check_out=check_out,
            status=Booking.STATUS_HELD,
            hold_expires_at=timezone.now() + timedelta(minutes=10)
        )

        count = get_available_rooms_count(self.room_type, check_in, check_out)
        self.assertEqual(count, 1)

    def test_check_availability_endpoint_success(self):
        """Valid parameters return 200 JSON with room data."""
        check_in = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        check_out = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')

        response = self.client.get(
            f'/availability/check/?room_type=deluxe-suite&check_in={check_in}&check_out={check_out}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['available'])
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['room_type_name'], 'Deluxe Suite')
        self.assertEqual(data['price_per_night'], '3500.00')
        self.assertEqual(data['nights'], 2)

    def test_check_availability_endpoint_validation_errors(self):
        """Invalid inputs return 400 JSON errors."""
        # Missing params
        res1 = self.client.get('/availability/check/')
        self.assertEqual(res1.status_code, 400)
        self.assertIn('error', res1.json())

        # Past check in
        past_in = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        future_out = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        res2 = self.client.get(
            f'/availability/check/?room_type=deluxe-suite&check_in={past_in}&check_out={future_out}')
        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.json()['error'],
                         'Check-in date cannot be in the past.')

        # Checkout before checkin
        in_date = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        out_date = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')
        res3 = self.client.get(
            f'/availability/check/?room_type=deluxe-suite&check_in={in_date}&check_out={out_date}')
        self.assertEqual(res3.status_code, 400)
        self.assertEqual(
            res3.json()['error'], 'Check-out date must be after check-in date.')


@override_settings(ALLOW_MOCK_PAYMENT=True)
class PublicBookingFlowTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.room_type = RoomType.objects.create(
            name="Deluxe Suite",
            slug="deluxe-suite",
            short_description="Spacious room",
            base_price_per_night=3500.00,
            max_occupancy=3
        )
        self.room = Room.objects.create(
            room_type=self.room_type, room_number="101")
        self.check_in = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        self.check_out = (date.today() + timedelta(days=7)
                          ).strftime('%Y-%m-%d')

    def test_send_otp_success_and_rate_limit(self):
        """OTP send creates record and enforces 30s cooldown."""
        res1 = self.client.post(
            '/bookings/otp/send/', data={'phone': '9876543210'}, content_type='application/json')
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()['success'])

        # Immediate resend should trigger 429
        res2 = self.client.post(
            '/bookings/otp/send/', data={'phone': '9876543210'}, content_type='application/json')
        self.assertEqual(res2.status_code, 429)
        self.assertIn('30 seconds', res2.json()['error'])

    def test_verify_otp_invalid_code_and_lockout(self):
        """Invalid OTP increments attempts and locks out after 5 tries."""
        self.client.post('/bookings/otp/send/',
                         data={'phone': '9876543210'}, content_type='application/json')

        payload = {
            'phone': '9876543210',
            'code': '000000',
            'guest_name': 'Alice Smith',
            'guest_email': 'alice@example.com',
            'room_type': 'deluxe-suite',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 2,
            'children': 0
        }

        for attempt in range(1, 6):
            res = self.client.post(
                '/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
            if attempt < 5:
                self.assertEqual(res.status_code, 400)
                self.assertIn('Invalid code', res.json()['error'])
            else:
                self.assertEqual(res.status_code, 429)
                self.assertIn('Too many failed attempts', res.json()['error'])

    def test_verify_and_hold_success(self):
        """Correct OTP creates held booking for 15 minutes."""
        self.client.post('/bookings/otp/send/',
                         data={'phone': '9876543210'}, content_type='application/json')
        otp_record = PhoneOTP.objects.filter(phone='9876543210').last()

        payload = {
            'phone': '9876543210',
            'code': otp_record.code,
            'guest_name': 'Jane Doe',
            'guest_email': 'jane@example.com',
            'room_type': 'deluxe-suite',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 2,
            'children': 1
        }

        res = self.client.post(
            '/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('booking_id', data)

        booking = Booking.objects.get(id=data['booking_id'])
        self.assertEqual(booking.status, Booking.STATUS_HELD)
        self.assertEqual(booking.adults, 2)
        self.assertEqual(booking.children, 1)
        self.assertIsNotNone(booking.hold_expires_at)

    def test_verify_and_hold_sold_out_409(self):
        """Returns 409 status code if room is booked before OTP verification."""
        # Create an existing confirmed booking that takes our only room
        Guest.objects.create(name="Prior Guest", phone="9999999999")
        Booking.objects.create(
            room=self.room,
            guest=Guest.objects.first(),
            check_in=self.check_in,
            check_out=self.check_out,
            status=Booking.STATUS_CONFIRMED
        )

        self.client.post('/bookings/otp/send/',
                         data={'phone': '9876543210'}, content_type='application/json')
        otp_record = PhoneOTP.objects.filter(phone='9876543210').last()

        payload = {
            'phone': '9876543210',
            'code': otp_record.code,
            'guest_name': 'Bob Ross',
            'guest_email': 'bob@example.com',
            'room_type': 'deluxe-suite',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 1,
            'children': 0
        }

        res = self.client.post(
            '/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 409)
        self.assertIn('sold out', res.json()['error'])

    def test_mock_pay_success(self):
        """Mock payment confirms held booking and reduces availability."""
        self.client.post('/bookings/otp/send/',
                         data={'phone': '9876543210'}, content_type='application/json')
        otp_record = PhoneOTP.objects.filter(phone='9876543210').last()

        payload = {
            'phone': '9876543210',
            'code': otp_record.code,
            'guest_name': 'Charlie',
            'guest_email': 'charlie@example.com',
            'room_type': 'deluxe-suite',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 2,
            'children': 0
        }
        res_hold = self.client.post(
            '/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        booking_id = res_hold.json()['booking_id']

        # Pay for booking with token
        res_pay = self.client.post(
            f'/bookings/{booking_id}/mock-pay/',
            data={'payment_token': res_hold.json()['payment_token']},
            content_type='application/json'
        )
        self.assertEqual(res_pay.status_code, 200)
        self.assertTrue(res_pay.json()['success'])

        booking = Booking.objects.get(id=booking_id)
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertIsNone(booking.hold_expires_at)

        # Availability after confirmation should now be 0
        avail_res = self.client.get(
            f'/availability/check/?room_type=deluxe-suite&check_in={self.check_in}&check_out={self.check_out}')
        self.assertEqual(avail_res.json()['count'], 0)

    def test_receipt_view_and_permissions(self):
        """Test receipt generation, token protection, and staff access."""
        from django.contrib.auth.models import User

        # 1. Create held booking
        self.client.post('/bookings/otp/send/',
                         data={'phone': '9876543210'}, content_type='application/json')
        otp_record = PhoneOTP.objects.filter(phone='9876543210').last()

        payload = {
            'phone': '9876543210',
            'code': otp_record.code,
            'guest_name': 'David',
            'guest_email': 'david@example.com',
            'room_type': 'deluxe-suite',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 2,
            'children': 0
        }
        res_hold = self.client.post(
            '/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        booking_id = res_hold.json()['booking_id']
        booking = Booking.objects.get(id=booking_id)

        # Access token auto-generated & total_amount saved
        self.assertTrue(booking.access_token)
        self.assertEqual(booking.total_amount, 7000.00)

        # Held booking receipt should return 404
        held_receipt_res = self.client.get(
            f'/bookings/{booking.id}/{booking.access_token}/receipt/')
        self.assertEqual(held_receipt_res.status_code, 404)

        # 2. Pay for booking with token
        res_pay = self.client.post(
            f'/bookings/{booking_id}/mock-pay/',
            data={'payment_token': res_hold.json()['payment_token']},
            content_type='application/json'
        )
        self.assertEqual(res_pay.status_code, 200)
        pay_data = res_pay.json()
        self.assertTrue(pay_data['success'])
        self.assertIn('receipt_url', pay_data)
        self.assertIn(booking.access_token, pay_data['receipt_url'])

        booking.refresh_from_db()
        self.assertTrue(booking.payment_reference.startswith('MOCK-'))
        self.assertIsNotNone(booking.paid_at)

        # Valid token access to confirmed receipt -> 200 OK
        valid_receipt_res = self.client.get(pay_data['receipt_url'])
        self.assertEqual(valid_receipt_res.status_code, 200)
        self.assertContains(valid_receipt_res, 'Official Booking Receipt')
        self.assertContains(valid_receipt_res, 'David')
        self.assertContains(valid_receipt_res, 'Room 101')
        self.assertContains(valid_receipt_res, '7000.00')

        # Invalid token access -> 404
        invalid_receipt_res = self.client.get(
            f'/bookings/{booking.id}/invalid_token_123/receipt/')
        self.assertEqual(invalid_receipt_res.status_code, 404)

        # Staff user access without valid token -> 200 OK
        from staff_panel.models import StaffProfile
        staff_user = User.objects.create_user(
            'admin', 'admin@example.com', 'password123', is_staff=False)
        StaffProfile.objects.create(
            user=staff_user, access_level=StaffProfile.ACCESS_BOOKINGS)
        self.client.login(username='admin', password='password123')
        staff_receipt_res = self.client.get(
            f'/bookings/{booking.id}/wrong_token/receipt/')
        self.assertEqual(staff_receipt_res.status_code, 200)
        self.assertContains(staff_receipt_res, 'Official Booking Receipt')

    def test_mark_guest_departed_action_and_early_checkout_availability(self):
        """Test admin action mark_guest_departed frees room availability early and enforces guard rails."""
        from django.contrib.admin.sites import AdminSite
        from bookings.admin import BookingAdmin
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage

        today = date.today()
        start = today
        end = today + timedelta(days=5)

        # 1. Create a confirmed booking spanning 5 days
        booking = Booking.objects.create(
            room=self.room,
            guest=Guest.objects.create(name="Eve", phone="9111111111"),
            check_in=start,
            check_out=end,
            status=Booking.STATUS_CONFIRMED
        )

        # Initially, room should be unavailable for dates inside start..end
        avail_before = get_available_rooms_count(
            self.room_type, start + timedelta(days=2), start + timedelta(days=4))
        self.assertEqual(avail_before, 0)

        # 2. Run mark_guest_departed admin action
        admin_obj = BookingAdmin(Booking, AdminSite())
        queryset = Booking.objects.filter(id=booking.id)

        factory = RequestFactory()
        req = factory.get('/')
        req.session = 'session'
        messages_storage = FallbackStorage(req)
        setattr(req, '_messages', messages_storage)

        admin_obj.mark_guest_departed(req, queryset)

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        self.assertIsNotNone(booking.actual_check_out)

        # 3. Room is now immediately available for requested dates
        avail_after = get_available_rooms_count(
            self.room_type, start + timedelta(days=2), start + timedelta(days=4))
        self.assertEqual(avail_after, 1)

        # 4. Test Guard Rails (Future check-in & non-confirmed bookings skipped)
        future_booking = Booking.objects.create(
            room=self.room,
            guest=Guest.objects.create(
                name="Future Guest", phone="9222222222"),
            check_in=today + timedelta(days=10),
            check_out=today + timedelta(days=15),
            status=Booking.STATUS_CONFIRMED
        )
        held_booking = Booking.objects.create(
            room=self.room,
            guest=Guest.objects.create(name="Held Guest", phone="9333333333"),
            check_in=today,
            check_out=today + timedelta(days=2),
            status=Booking.STATUS_HELD
        )

        qs_guard = Booking.objects.filter(
            id__in=[future_booking.id, held_booking.id])
        admin_obj.mark_guest_departed(req, qs_guard)

        future_booking.refresh_from_db()
        held_booking.refresh_from_db()
        self.assertEqual(future_booking.status, Booking.STATUS_CONFIRMED)
        self.assertEqual(held_booking.status, Booking.STATUS_HELD)


class CancellationServiceTestCase(TestCase):
    """Tests for cancel_booking() service function."""

    def setUp(self):
        self.room_type = RoomType.objects.create(
            name="Deluxe Suite",
            slug="deluxe-suite-cancel",
            short_description="Spacious room",
            base_price_per_night=3500.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_type=self.room_type, room_number="201")
        self.guest = Guest.objects.create(
            name="Cancel Guest", phone="+919999000001")

    def _make_booking(self, status, hold_expires_at=None):
        return Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=date.today() + timedelta(days=3),
            check_out=date.today() + timedelta(days=5),
            status=status,
            hold_expires_at=hold_expires_at,
            total_amount=7000.00,
        )

    def test_cancel_held_booking_succeeds(self):
        """Cancelling a held booking sets status, cancelled_at, and reason."""
        from bookings.services import cancel_booking
        booking = self._make_booking(
            Booking.STATUS_HELD, hold_expires_at=timezone.now() + timedelta(minutes=10))
        success, msg = cancel_booking(booking, reason='Guest changed mind')
        self.assertTrue(success)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)
        self.assertEqual(booking.cancellation_reason, 'Guest changed mind')

    def test_cancel_confirmed_booking_succeeds(self):
        """Cancelling a confirmed booking works and frees availability."""
        from bookings.services import cancel_booking
        booking = self._make_booking(Booking.STATUS_CONFIRMED)
        check_in = booking.check_in
        check_out = booking.check_out

        # Room should be unavailable before cancellation
        count_before = get_available_rooms_count(
            self.room_type, check_in, check_out)
        self.assertEqual(count_before, 0)

        success, msg = cancel_booking(booking)
        self.assertTrue(success)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)

        # Room should be available after cancellation
        count_after = get_available_rooms_count(
            self.room_type, check_in, check_out)
        self.assertEqual(count_after, 1)

    def test_cancel_already_cancelled_rejected(self):
        """Attempting to cancel an already-cancelled booking is rejected."""
        from bookings.services import cancel_booking
        booking = self._make_booking(Booking.STATUS_CANCELLED)
        success, msg = cancel_booking(booking)
        self.assertFalse(success)
        self.assertIn('cannot cancel', msg.lower())

    def test_cancel_completed_booking_rejected(self):
        """Attempting to cancel a completed booking is rejected."""
        from bookings.services import cancel_booking
        booking = self._make_booking(Booking.STATUS_COMPLETED)
        success, msg = cancel_booking(booking)
        self.assertFalse(success)
        self.assertIn('cannot cancel', msg.lower())

    def test_cancel_no_reason_sets_empty_string(self):
        """Cancelling without a reason stores an empty string, not None."""
        from bookings.services import cancel_booking
        booking = self._make_booking(Booking.STATUS_CONFIRMED)
        success, _ = cancel_booking(booking)
        self.assertTrue(success)
        booking.refresh_from_db()
        self.assertEqual(booking.cancellation_reason, '')


class ExpireStaleHoldsTestCase(TestCase):
    """Tests for expire_stale_holds() service function."""

    def setUp(self):
        self.room_type = RoomType.objects.create(
            name="Standard Room",
            slug="standard-expire-test",
            short_description="Standard",
            base_price_per_night=2000.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_type=self.room_type, room_number="301")
        self.guest = Guest.objects.create(
            name="Expire Guest", phone="+919999000002")

    def _make_held(self, expires_at):
        return Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=date.today() + timedelta(days=1),
            check_out=date.today() + timedelta(days=3),
            status=Booking.STATUS_HELD,
            hold_expires_at=expires_at,
            total_amount=4000.00,
        )

    def test_expired_hold_gets_cancelled(self):
        """An expired held booking is cancelled by expire_stale_holds."""
        from bookings.services import expire_stale_holds
        booking = self._make_held(timezone.now() - timedelta(minutes=1))
        count = expire_stale_holds()
        self.assertEqual(count, 1)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)
        self.assertIn('expired', booking.cancellation_reason.lower())

    def test_active_hold_not_cancelled(self):
        """An active (unexpired) held booking is NOT touched by expire_stale_holds."""
        from bookings.services import expire_stale_holds
        booking = self._make_held(timezone.now() + timedelta(minutes=10))
        count = expire_stale_holds()
        self.assertEqual(count, 0)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_HELD)

    def test_confirmed_booking_not_touched(self):
        """Confirmed bookings are never cancelled by expire_stale_holds."""
        from bookings.services import expire_stale_holds
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=date.today() + timedelta(days=1),
            check_out=date.today() + timedelta(days=3),
            status=Booking.STATUS_CONFIRMED,
        )
        count = expire_stale_holds()
        self.assertEqual(count, 0)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)

    def test_already_cancelled_not_touched(self):
        """Already-cancelled bookings are never re-processed."""
        from bookings.services import expire_stale_holds
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=date.today() + timedelta(days=1),
            check_out=date.today() + timedelta(days=3),
            status=Booking.STATUS_CANCELLED,
            cancelled_at=timezone.now(),
            cancellation_reason='Prior cancellation',
        )
        count = expire_stale_holds()
        self.assertEqual(count, 0)
        booking.refresh_from_db()
        self.assertEqual(booking.cancellation_reason, 'Prior cancellation')


class ReceiptPdfAccessControlTestCase(TestCase):
    """Tests for the receipt PDF endpoint access control."""

    def setUp(self):
        self.room_type = RoomType.objects.create(
            name="Deluxe Suite",
            slug="deluxe-pdf-test",
            short_description="Spacious room",
            base_price_per_night=3500.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_type=self.room_type, room_number="401")
        self.guest = Guest.objects.create(
            name="PDF Guest", phone="+919999000003")

    def _make_confirmed_booking(self):
        return Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=date.today() + timedelta(days=1),
            check_out=date.today() + timedelta(days=3),
            status=Booking.STATUS_CONFIRMED,
            payment_reference='MOCK-PDF-001',
            total_amount=7000.00,
        )

    def test_valid_token_returns_pdf(self):
        """A valid access token returns 200 with application/pdf content type."""
        try:
            import weasyprint  # noqa: F401
        except (ImportError, OSError):
            self.skipTest(
                'WeasyPrint not available in this environment — PDF rendering skipped.')

        booking = self._make_confirmed_booking()
        url = f'/bookings/{booking.id}/{booking.access_token}/receipt.pdf'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn(f'CH-{booking.id:05d}', response['Content-Disposition'])

    def test_invalid_token_returns_404(self):
        """An invalid token returns 404 for the PDF endpoint."""
        booking = self._make_confirmed_booking()
        url = f'/bookings/{booking.id}/wrong-token-xyz/receipt.pdf'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_staff_bypass_without_token(self):
        """Staff with bookings access can fetch the PDF with any token value."""
        try:
            import weasyprint  # noqa: F401
        except (ImportError, OSError):
            self.skipTest(
                'WeasyPrint not available in this environment — PDF rendering skipped.')

        from django.contrib.auth.models import User
        from staff_panel.models import StaffProfile
        booking = self._make_confirmed_booking()
        staff_user = User.objects.create_user(
            'pdf_staff', password='Password123!')
        StaffProfile.objects.create(
            user=staff_user, access_level=StaffProfile.ACCESS_BOOKINGS)
        self.client.login(username='pdf_staff', password='Password123!')
        url = f'/bookings/{booking.id}/wrong-token/receipt.pdf'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_held_booking_pdf_returns_404(self):
        """PDF endpoint returns 404 for held (unconfirmed) bookings."""
        booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=date.today() + timedelta(days=1),
            check_out=date.today() + timedelta(days=3),
            status=Booking.STATUS_HELD,
            hold_expires_at=timezone.now() + timedelta(minutes=15),
        )
        url = f'/bookings/{booking.id}/{booking.access_token}/receipt.pdf'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class BookingPageTestCase(TestCase):
    def setUp(self):
        self.room_type = RoomType.objects.create(
            name="Standard Room",
            slug="standard-room",
            short_description="Cozy room",
            base_price_per_night=2200.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_type=self.room_type, room_number="101")
        self.guest = Guest.objects.create(
            name="Alice", phone="+919876543210")

    def test_booking_page_renders_with_valid_parameters(self):
        check_in = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
        check_out = (date.today() + timedelta(days=4)).strftime('%Y-%m-%d')
        response = self.client.get(
            f'/booking/?room_type=standard-room&check_in={check_in}&check_out={check_out}&adults=2&children=0'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/booking_page.html')
        self.assertTrue(response.context['has_valid_selection'])
        self.assertTrue(response.context['is_available'])
        self.assertEqual(response.context['nights'], 2)
        self.assertEqual(response.context['price_per_night'], "2200.00")
        self.assertEqual(response.context['total_amount'], "4400.00")

    def test_booking_page_renders_without_parameters(self):
        response = self.client.get('/booking/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/booking_page.html')
        self.assertFalse(response.context['has_valid_selection'])

    def test_booking_page_with_past_checkin(self):
        past_date = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        future_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        response = self.client.get(
            f'/booking/?room_type=standard-room&check_in={past_date}&check_out={future_date}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_valid_selection'])
        self.assertIn("past", response.context['error_message'].lower())

    def test_booking_page_when_fully_booked(self):
        check_in = date.today() + timedelta(days=3)
        check_out = check_in + timedelta(days=2)
        Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=check_in,
            check_out=check_out,
            status=Booking.STATUS_CONFIRMED
        )
        response = self.client.get(
            f'/booking/?room_type=standard-room&check_in={check_in.strftime("%Y-%m-%d")}&check_out={check_out.strftime("%Y-%m-%d")}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_available'])
        self.assertIn("fully booked", response.context['error_message'].lower())


import threading
import unittest
from django.db import connection
from django.test import TransactionTestCase, Client
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from bookings.payment_gateway import MockPaymentGateway


class ConcurrencyDoubleBookingTestCase(TransactionTestCase):
    @unittest.skipIf(connection.vendor == 'sqlite', "Row locking (select_for_update) is a no-op on SQLite and requires PostgreSQL")
    def test_verify_and_hold_double_booking_race_condition(self):
        """
        Concurrency test against PostgreSQL (coral_heights_db):
        When exactly 1 room remains, two simultaneous threads calling verify_and_hold
        must produce exactly one held booking and one 409 Conflict.
        """
        check_in = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
        check_out = (date.today() + timedelta(days=12)).strftime('%Y-%m-%d')

        room_type = RoomType.objects.create(
            name="Single Room Only",
            slug="single-race-room",
            base_price_per_night=2000.00,
            max_occupancy=2
        )
        Room.objects.create(room_type=room_type, room_number="RACE-101")

        PhoneOTP.objects.create(
            phone="9100000001",
            code="111111",
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        PhoneOTP.objects.create(
            phone="9100000002",
            code="222222",
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        results = []
        barrier = threading.Barrier(2)

        def attempt_hold(phone, code, guest_name):
            from django.db import connection
            connection.close()
            client = Client()
            payload = {
                'phone': phone,
                'code': code,
                'guest_name': guest_name,
                'room_type': 'single-race-room',
                'check_in': check_in,
                'check_out': check_out,
                'adults': 2,
                'children': 0
            }
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            res = client.post(
                '/bookings/otp/verify-and-hold/',
                data=payload,
                content_type='application/json'
            )
            results.append((res.status_code, res.json()))
            connection.close()

        t1 = threading.Thread(target=attempt_hold, args=("9100000001", "111111", "Guest Alpha"))
        t2 = threading.Thread(target=attempt_hold, args=("9100000002", "222222", "Guest Beta"))

        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        status_codes = [r[0] for r in results]
        self.assertEqual(len(status_codes), 2)
        self.assertIn(200, status_codes)
        self.assertIn(409, status_codes)

        # Assert exactly one hold was created in the database
        holds_count = Booking.objects.filter(
            room__room_type=room_type,
            status=Booking.STATUS_HELD
        ).count()
        self.assertEqual(holds_count, 1)


class InputValidationHardeningTestCase(TestCase):
    def setUp(self):
        self.room_type = RoomType.objects.create(
            name="Standard Test Room",
            slug="standard-test-room",
            base_price_per_night=2000.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_type=self.room_type,
            room_number="V101"
        )
        self.check_in = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        self.check_out = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        self.otp = PhoneOTP.objects.create(
            phone="9876543210",
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=10)
        )

    def test_verify_and_hold_invalid_non_numeric_adults(self):
        payload = {
            'phone': '9876543210',
            'code': '123456',
            'guest_name': 'Test Guest',
            'room_type': 'standard-test-room',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 'abc',
            'children': 0
        }
        res = self.client.post('/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("valid numbers", res.json()['error'])

    def test_verify_and_hold_invalid_zero_adults(self):
        payload = {
            'phone': '9876543210',
            'code': '123456',
            'guest_name': 'Test Guest',
            'room_type': 'standard-test-room',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 0,
            'children': 0
        }
        res = self.client.post('/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("at least 1", res.json()['error'])

    def test_verify_and_hold_invalid_negative_children(self):
        payload = {
            'phone': '9876543210',
            'code': '123456',
            'guest_name': 'Test Guest',
            'room_type': 'standard-test-room',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 1,
            'children': -1
        }
        res = self.client.post('/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("negative", res.json()['error'])

    def test_verify_and_hold_exceeds_max_occupancy(self):
        # max_occupancy is 2. 2 adults + 1 child = 3 > 2
        payload = {
            'phone': '9876543210',
            'code': '123456',
            'guest_name': 'Test Guest',
            'room_type': 'standard-test-room',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 2,
            'children': 1
        }
        res = self.client.post('/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceed maximum capacity", res.json()['error'])

    def test_check_availability_exceeds_max_occupancy(self):
        res = self.client.get(
            f'/availability/check/?room_type=standard-test-room&check_in={self.check_in}&check_out={self.check_out}&adults=3&children=0'
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceed maximum capacity", res.json()['error'])

    def test_check_availability_invalid_non_numeric_guests(self):
        res = self.client.get(
            f'/availability/check/?room_type=standard-test-room&check_in={self.check_in}&check_out={self.check_out}&adults=bad&children=0'
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("valid numbers", res.json()['error'])

    def test_booking_page_exceeds_max_occupancy(self):
        res = self.client.get(
            f'/booking/?room_type=standard-test-room&check_in={self.check_in}&check_out={self.check_out}&adults=3&children=1'
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['has_valid_selection'])
        self.assertIn("exceed maximum capacity", res.context['error_message'])


class OTPProtectionHardeningTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.room_type = RoomType.objects.create(
            name="OTP Test Suite",
            slug="otp-test-suite",
            base_price_per_night=3000.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_type=self.room_type,
            room_number="OTP-1"
        )
        self.check_in = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        self.check_out = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')

    def test_failed_hold_preserves_otp(self):
        """If room is sold out, verify_and_hold must NOT consume the OTP."""
        # Book the room to sell it out
        guest = Guest.objects.create(name="Existing", phone="9999999999")
        Booking.objects.create(
            room=self.room,
            guest=guest,
            check_in=date.today() + timedelta(days=5),
            check_out=date.today() + timedelta(days=7),
            status=Booking.STATUS_CONFIRMED
        )

        otp = PhoneOTP.objects.create(
            phone="9876543210",
            code="654321",
            expires_at=timezone.now() + timedelta(minutes=10),
            is_verified=False
        )

        payload = {
            'phone': '9876543210',
            'code': '654321',
            'guest_name': 'OTP Guest',
            'room_type': 'otp-test-suite',
            'check_in': self.check_in,
            'check_out': self.check_out,
            'adults': 2,
            'children': 0
        }
        res = self.client.post('/bookings/otp/verify-and-hold/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 409)

        # Ensure OTP was NOT burned
        otp.refresh_from_db()
        self.assertFalse(otp.is_verified)

    def test_otp_generation_uses_secrets_six_digits(self):
        """Assert OTP codes are always exactly 6 digits."""
        res = self.client.post('/bookings/otp/send/', data={'phone': '9876543211'}, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        otp = PhoneOTP.objects.filter(phone='9876543211').latest('created_at')
        self.assertEqual(len(otp.code), 6)
        self.assertTrue(otp.code.isdigit())
        self.assertTrue(100000 <= int(otp.code) <= 999999)

    def test_send_otp_per_ip_rate_limiting(self):
        """Max 5 sends per IP per 10 minutes. 6th call from same IP returns 429."""
        cache.clear()
        client_ip = "192.168.10.50"
        for i in range(5):
            phone = f"98765432{i:02d}"
            res = self.client.post(
                '/bookings/otp/send/',
                data={'phone': phone},
                content_type='application/json',
                REMOTE_ADDR=client_ip
            )
            self.assertEqual(res.status_code, 200)

        # 6th attempt from the same IP
        res_sixth = self.client.post(
            '/bookings/otp/send/',
            data={'phone': '9876543299'},
            content_type='application/json',
            REMOTE_ADDR=client_ip
        )
        self.assertEqual(res_sixth.status_code, 429)
        self.assertIn("Too many verification code requests", res_sixth.json()['error'])


@override_settings(ALLOW_MOCK_PAYMENT=True)
class PaymentSafetyHardeningTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.room_type = RoomType.objects.create(
            name="Payment Safety Suite",
            slug="pay-safety-suite",
            base_price_per_night=3000.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            room_type=self.room_type,
            room_number="PAY-1"
        )
        self.guest = Guest.objects.create(name="Pay Guest", phone="9876543210")
        self.booking = Booking.objects.create(
            room=self.room,
            guest=self.guest,
            check_in=date.today() + timedelta(days=5),
            check_out=date.today() + timedelta(days=7),
            adults=2,
            children=0,
            status=Booking.STATUS_HELD,
            hold_expires_at=timezone.now() + timedelta(minutes=15),
            total_amount=6000.00
        )

    def test_mock_pay_without_token_returns_403(self):
        res = self.client.post(f'/bookings/{self.booking.id}/mock-pay/', data={}, content_type='application/json')
        self.assertEqual(res.status_code, 403)
        self.assertIn("payment token", res.json()['error'].lower())

    def test_mock_pay_with_wrong_token_returns_403(self):
        res = self.client.post(
            f'/bookings/{self.booking.id}/mock-pay/',
            data={'payment_token': 'wrong-fake-token'},
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("payment token", res.json()['error'].lower())

    def test_mock_pay_with_valid_token_succeeds(self):
        res = self.client.post(
            f'/bookings/{self.booking.id}/mock-pay/',
            data={'payment_token': self.booking.access_token},
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_CONFIRMED)

    def test_mock_pay_double_confirmation_prevented(self):
        # First confirmation
        res1 = self.client.post(
            f'/bookings/{self.booking.id}/mock-pay/',
            data={'payment_token': self.booking.access_token},
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)

        # Second confirmation attempt on already confirmed booking
        res2 = self.client.post(
            f'/bookings/{self.booking.id}/mock-pay/',
            data={'payment_token': self.booking.access_token},
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("no longer held", res2.json()['error'].lower())

    def test_mock_gateway_refuses_when_debug_false_without_allow_mock_payment(self):
        from django.conf import settings
        with self.settings(DEBUG=False, ALLOW_MOCK_PAYMENT=False):
            with self.assertRaises(ImproperlyConfigured):
                MockPaymentGateway()

    def test_mock_gateway_allowed_when_allow_mock_payment_true(self):
        with self.settings(DEBUG=False, ALLOW_MOCK_PAYMENT=True):
            gateway = MockPaymentGateway()
            ref = gateway.confirm_payment(self.booking)
            self.assertTrue(ref.startswith('MOCK-'))


class SettingsHardeningTestCase(TestCase):
    def test_insecure_secret_key_raises_when_debug_false(self):
        from config.settings import INSECURE_DEV_SECRET_KEY

        def check_secret_key_security(debug_flag, key):
            if not debug_flag and (not key or key == INSECURE_DEV_SECRET_KEY):
                raise ImproperlyConfigured("SECRET_KEY must be configured with a secure, unique value when DEBUG is False.")

        # Insecure default dev key when DEBUG=False raises ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            check_secret_key_security(False, INSECURE_DEV_SECRET_KEY)

        # Empty key when DEBUG=False raises ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            check_secret_key_security(False, "")

        # Valid in local development (DEBUG=True)
        check_secret_key_security(True, INSECURE_DEV_SECRET_KEY)

        # Valid in production with secure key
        check_secret_key_security(False, "production-secret-key-xyz-123")


