from datetime import date, timedelta
from django.test import TestCase
from django.core.cache import cache
from enquiries.models import Enquiry


class EnquiryFormTestCase(TestCase):
    def setUp(self):
        cache.clear()
    def test_valid_enquiry_submission(self):
        """Submitting valid data creates an Enquiry row with status='new'."""
        preferred_date = (date.today() + timedelta(days=10)
                          ).strftime('%Y-%m-%d')
        data = {
            'function_type': 'wedding',
            'preferred_date': preferred_date,
            'guest_count': 150,
            'contact_name': 'Ramesh Kumar',
            'contact_phone': '9876543210',
            'menu_requirements': 'Traditional Kerala Sadya',
            'notes': 'Stage arrangement required',
        }

        response = self.client.post('/enquiries/submit/', data)
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertTrue(res_data['success'])

        # Verify Enquiry in database
        self.assertEqual(Enquiry.objects.count(), 1)
        enquiry = Enquiry.objects.first()
        self.assertEqual(enquiry.contact_name, 'Ramesh Kumar')
        self.assertEqual(enquiry.contact_phone, '9876543210')
        self.assertEqual(enquiry.function_type, 'wedding')
        self.assertEqual(enquiry.guest_count, 150)
        self.assertEqual(enquiry.status, Enquiry.STATUS_NEW)

    def test_invalid_enquiry_submission_missing_fields(self):
        """Missing required fields returns 400 with validation errors and no row created."""
        data = {
            'function_type': 'birthday',
            # missing preferred_date, guest_count, contact_name, contact_phone
        }

        response = self.client.post('/enquiries/submit/', data)
        self.assertEqual(response.status_code, 400)
        res_data = response.json()
        self.assertFalse(res_data['success'])
        self.assertIn('contact_name', res_data['errors'])
        self.assertIn('contact_phone', res_data['errors'])
        self.assertIn('preferred_date', res_data['errors'])

        self.assertEqual(Enquiry.objects.count(), 0)

    def test_invalid_phone_number_not_10_digits(self):
        """Entering phone number that is not 10 digits returns a validation error."""
        preferred_date = (date.today() + timedelta(days=10)
                          ).strftime('%Y-%m-%d')
        data = {
            'function_type': 'wedding',
            'preferred_date': preferred_date,
            'guest_count': 50,
            'contact_name': 'Ananthan',
            'contact_phone': '987654',  # only 6 digits
        }

        response = self.client.post('/enquiries/submit/', data)
        self.assertEqual(response.status_code, 400)
        res_data = response.json()
        self.assertFalse(res_data['success'])
        self.assertIn('contact_phone', res_data['errors'])
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_past_date_validation_error(self):
        """Selecting a date in the past returns a validation error."""
        past_date = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        data = {
            'function_type': 'birthday',
            'preferred_date': past_date,
            'guest_count': 20,
            'contact_name': 'Anita Roy',
            'contact_phone': '9876500000',
        }

        response = self.client.post('/enquiries/submit/', data)
        self.assertEqual(response.status_code, 400)
        res_data = response.json()
        self.assertFalse(res_data['success'])
        self.assertIn('preferred_date', res_data['errors'])
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_get_method_not_allowed(self):
        """GET request to /enquiries/submit/ returns 405 Method Not Allowed."""
        response = self.client.get('/enquiries/submit/')
        self.assertEqual(response.status_code, 405)

    def test_enquiry_submission_logs_warning_when_email_fails(self):
        """When email sending fails, a warning is logged and the enquiry is still saved."""
        from unittest.mock import patch
        preferred_date = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
        data = {
            'function_type': 'wedding',
            'preferred_date': preferred_date,
            'guest_count': 150,
            'contact_name': 'Ramesh Kumar',
            'contact_phone': '9876543210',
            'menu_requirements': 'Traditional Kerala Sadya',
            'notes': 'Stage arrangement required',
        }

        with patch('enquiries.views.send_mail', side_effect=Exception('SMTP connection failed')):
            with self.assertLogs('enquiries.views', level='WARNING') as cm:
                response = self.client.post('/enquiries/submit/', data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'])
                self.assertTrue(any('Failed to send enquiry notification email' in output for output in cm.output))
                enquiry = Enquiry.objects.first()
                self.assertFalse(enquiry.notification_sent)
                self.assertIn('SMTP connection failed', enquiry.notification_error)

    def test_enquiry_throttling(self):
        """Enquiry submissions are throttled after 5 requests from the same IP."""
        from django.core.cache import cache
        cache.clear()
        preferred_date = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
        data = {
            'function_type': 'birthday',
            'preferred_date': preferred_date,
            'guest_count': 20,
            'contact_name': 'Test Throttling',
            'contact_phone': '9876543210',
        }
        for _ in range(5):
            res = self.client.post('/enquiries/submit/', data)
            self.assertEqual(res.status_code, 200)

        # 6th request
        res = self.client.post('/enquiries/submit/', data)
        self.assertEqual(res.status_code, 429)

    def test_browser_html_submission_invalid_preserves_session(self):
        """Ordinary HTML submission with errors stores submitted values and errors in session."""
        data = {
            'function_type': 'birthday',
            'contact_name': 'Anita',
            'contact_phone': '123', # invalid phone
        }
        response = self.client.post(
            '/enquiries/submit/',
            data,
            HTTP_ACCEPT='text/html,application/xhtml+xml',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/#enquiry', response.url)
        session = self.client.session
        self.assertIn('enquiry_errors', session)
        self.assertIn('contact_phone', session['enquiry_errors'])
        self.assertIn('enquiry_data', session)
        self.assertEqual(session['enquiry_data']['contact_name'], 'Anita')

