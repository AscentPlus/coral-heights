from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal

from staff_panel.models import StaffProfile
from hotel_info.models import (
    HotelInfo, RestaurantInfo, MenuCategory, MenuItem,
    NearbyPlace, ChatFAQ, UnansweredQuestion
)


class HotelInfoModelAndSingletonTests(TestCase):
    def test_hotel_info_singleton_on_fresh_db(self):
        """HotelInfo.load() creates and returns a singleton instance on a fresh DB."""
        self.assertEqual(HotelInfo.objects.count(), 0)
        info1 = HotelInfo.load()
        self.assertIsNotNone(info1)
        self.assertEqual(HotelInfo.objects.count(), 1)
        self.assertEqual(info1.check_in_time, "12:00 PM")
        self.assertEqual(info1.check_out_time, "11:00 AM")

        info2 = HotelInfo.load()
        self.assertEqual(info1.pk, info2.pk)
        self.assertEqual(HotelInfo.objects.count(), 1)

    def test_restaurant_info_singleton_on_fresh_db(self):
        """RestaurantInfo.load() creates and returns a singleton instance on a fresh DB."""
        self.assertEqual(RestaurantInfo.objects.count(), 0)
        rest1 = RestaurantInfo.load()
        self.assertIsNotNone(rest1)
        self.assertEqual(RestaurantInfo.objects.count(), 1)

        rest2 = RestaurantInfo.load()
        self.assertEqual(rest1.pk, rest2.pk)
        self.assertEqual(RestaurantInfo.objects.count(), 1)


class HotelInfoStaffViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Superuser
        self.superuser = User.objects.create_superuser(
            username='admin_super', email='admin@test.com', password='Password123!'
        )

        # Website-only staff
        self.web_user = User.objects.create_user(
            username='staff_web', password='Password123!', is_staff=False
        )
        StaffProfile.objects.create(
            user=self.web_user, access_level=StaffProfile.ACCESS_WEBSITE
        )

        # Bookings-only staff
        self.booking_user = User.objects.create_user(
            username='staff_booking', password='Password123!', is_staff=False
        )
        StaffProfile.objects.create(
            user=self.booking_user, access_level=StaffProfile.ACCESS_BOOKINGS
        )

    def test_permission_boundary_bookings_staff_blocked(self):
        """Bookings-only staff cannot reach any hotel_info staff pages (HTTP 403)."""
        self.client.login(username='staff_booking', password='Password123!')

        routes = [
            reverse('staff_panel:website_hotel_details'),
            reverse('staff_panel:website_restaurant_details'),
            reverse('staff_panel:website_menu'),
            reverse('staff_panel:website_nearby_places'),
            reverse('staff_panel:website_faqs'),
            reverse('staff_panel:website_unanswered_questions'),
        ]
        for url in routes:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, f"Expected 403 for bookings staff on {url}")

    def test_permission_boundary_website_staff_allowed(self):
        """Website-content staff can access all hotel_info pages (HTTP 200)."""
        self.client.login(username='staff_web', password='Password123!')

        routes = [
            reverse('staff_panel:website_hotel_details'),
            reverse('staff_panel:website_restaurant_details'),
            reverse('staff_panel:website_menu'),
            reverse('staff_panel:website_nearby_places'),
            reverse('staff_panel:website_faqs'),
            reverse('staff_panel:website_unanswered_questions'),
        ]
        for url in routes:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Expected 200 for website staff on {url}")

    def test_hotel_details_form_save_and_update(self):
        """Hotel details form updates singleton HotelInfo attributes."""
        self.client.login(username='staff_web', password='Password123!')

        url = reverse('staff_panel:website_hotel_details')
        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)

        post_res = self.client.post(url, {
            'check_in_time': '01:00 PM',
            'check_out_time': '11:30 AM',
            'address_note': 'Near Ambalapuzha Temple Junction',
            'parking_info': 'Free valet parking available for all guests',
            'wifi_info': 'Fast Wi-Fi in rooms and restaurant',
            'payment_methods': 'Cash, UPI, Visa, Mastercard',
            'languages_spoken': 'English, Malayalam, Hindi',
            'pet_policy': 'No pets allowed except certified guide dogs',
            'extra_notes': 'Strictly non-smoking inside rooms',
            'rate_note': 'Rates vary by season. Check availability for exact price.',
        })
        self.assertRedirects(post_res, url)

        info = HotelInfo.load()
        self.assertEqual(info.check_in_time, '01:00 PM')
        self.assertEqual(info.check_out_time, '11:30 AM')
        self.assertEqual(info.parking_info, 'Free valet parking available for all guests')
        self.assertEqual(info.languages_spoken, 'English, Malayalam, Hindi')

    def test_restaurant_details_form_save_and_update(self):
        """Restaurant details form updates singleton RestaurantInfo attributes."""
        self.client.login(username='staff_web', password='Password123!')

        url = reverse('staff_panel:website_restaurant_details')
        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)

        post_res = self.client.post(url, {
            'name': 'Coral Dining Hall',
            'cuisine_description': 'Authentic Kuttanad & Coastal Kerala cuisine',
            'breakfast_hours': '7:00 AM – 10:00 AM',
            'lunch_hours': '12:30 PM – 3:30 PM',
            'dinner_hours': '7:00 PM – 10:30 PM',
            'thattukada_hours': '5:00 PM – 9:00 PM',
            'room_service_info': 'Available 24 hours for tea/coffee, meals during dining hours',
            'extra_notes': 'Vegetarian and Jain meals available on request',
        })
        self.assertRedirects(post_res, url)

        rest = RestaurantInfo.load()
        self.assertEqual(rest.name, 'Coral Dining Hall')
        self.assertEqual(rest.breakfast_hours, '7:00 AM – 10:00 AM')
        self.assertEqual(rest.thattukada_hours, '5:00 PM – 9:00 PM')

    def test_menu_category_and_items_crud(self):
        """MenuCategory and MenuItem creation, editing, filtering, and deletion."""
        self.client.login(username='staff_web', password='Password123!')
        menu_url = reverse('staff_panel:website_menu')

        # 1. Create Category
        res_cat = self.client.post(menu_url, {
            'action': 'create_category',
            'name': 'Kerala Specialties',
            'display_order': 1,
        })
        self.assertRedirects(res_cat, menu_url)
        category = MenuCategory.objects.get(name='Kerala Specialties')

        # 2. Edit Category
        res_cat_edit = self.client.post(menu_url, {
            'action': 'edit_category',
            'category_id': category.id,
            'name': 'Kerala Traditional Delicacies',
            'display_order': 2,
        })
        self.assertRedirects(res_cat_edit, menu_url)
        category.refresh_from_db()
        self.assertEqual(category.name, 'Kerala Traditional Delicacies')

        # 3. Create Menu Items
        res_item1 = self.client.post(menu_url, {
            'action': 'create_item',
            'category': category.id,
            'name': 'Karimeen Pollichathu',
            'description': 'Marinated pearl spot wrapped in banana leaf',
            'price': '350.00',
            'is_veg': False,
            'is_available': True,
            'display_order': 1,
        })
        self.assertEqual(res_item1.status_code, 302)
        item1 = MenuItem.objects.get(name='Karimeen Pollichathu')
        self.assertEqual(item1.price, Decimal('350.00'))
        self.assertFalse(item1.is_veg)

        res_item2 = self.client.post(menu_url, {
            'action': 'create_item',
            'category': category.id,
            'name': 'Appam with Stew',
            'description': 'Vegetable stew with coconut milk',
            'price': '180.00',
            'is_veg': True,
            'is_available': True,
            'display_order': 2,
        })
        self.assertEqual(res_item2.status_code, 302)
        item2 = MenuItem.objects.get(name='Appam with Stew')
        self.assertTrue(item2.is_veg)

        # 4. Filter by category
        filter_res = self.client.get(f"{menu_url}?category={category.id}")
        self.assertEqual(filter_res.status_code, 200)
        self.assertContains(filter_res, 'Karimeen Pollichathu')
        self.assertContains(filter_res, 'Appam with Stew')

        # 5. Edit Menu Item
        res_item_edit = self.client.post(menu_url, {
            'action': 'edit_item',
            'item_id': item1.id,
            'category': category.id,
            'name': 'Karimeen Pollichathu Special',
            'description': 'Fresh backwaters pearl spot',
            'price': '380.00',
            'is_veg': False,
            'is_available': False,
            'display_order': 1,
        })
        self.assertEqual(res_item_edit.status_code, 302)
        item1.refresh_from_db()
        self.assertEqual(item1.name, 'Karimeen Pollichathu Special')
        self.assertEqual(item1.price, Decimal('380.00'))
        self.assertFalse(item1.is_available)

        # 6. Delete Menu Item
        item_delete_url = reverse('staff_panel:website_menu_item_delete', kwargs={'pk': item2.id})
        res_del_item = self.client.post(item_delete_url)
        self.assertEqual(res_del_item.status_code, 302)
        self.assertFalse(MenuItem.objects.filter(id=item2.id).exists())

    def test_menu_category_delete_guard(self):
        """Deleting a MenuCategory that still has items is blocked with a friendly message."""
        self.client.login(username='staff_web', password='Password123!')

        cat = MenuCategory.objects.create(name='Seafood', display_order=1)
        MenuItem.objects.create(
            category=cat, name='Fish Curry', price=Decimal('220.00'), is_veg=False
        )

        cat_delete_url = reverse('staff_panel:website_menu_category_delete', kwargs={'pk': cat.id})
        res = self.client.post(cat_delete_url, follow=True)
        self.assertEqual(res.status_code, 200)

        # Category MUST still exist
        self.assertTrue(MenuCategory.objects.filter(id=cat.id).exists())
        self.assertContains(res, "Cannot delete category &#x27;Seafood&#x27; because it contains 1 menu item")

        # Now remove item and verify deletion succeeds
        MenuItem.objects.filter(category=cat).delete()
        res_clean = self.client.post(cat_delete_url)
        self.assertRedirects(res_clean, reverse('staff_panel:website_menu'))
        self.assertFalse(MenuCategory.objects.filter(id=cat.id).exists())

    def test_nearby_places_crud(self):
        """NearbyPlace creation, editing, and deletion."""
        self.client.login(username='staff_web', password='Password123!')
        url = reverse('staff_panel:website_nearby_places')

        # 1. Create
        res_create = self.client.post(url, {
            'action': 'create',
            'place_type': 'railway_station',
            'name': 'Ambalapuzha Railway Station',
            'distance_km': '1.80',
            'travel_time': '5 min by auto',
            'directions_note': 'Head north on NH 66',
            'display_order': 1,
        })
        self.assertRedirects(res_create, url)
        place = NearbyPlace.objects.get(name='Ambalapuzha Railway Station')
        self.assertEqual(place.distance_km, Decimal('1.80'))
        self.assertEqual(place.place_type, 'railway_station')

        # 2. Edit
        res_edit = self.client.post(url, {
            'action': 'edit',
            'place_id': place.id,
            'place_type': 'railway_station',
            'name': 'Ambalapuzha Railway Station (AMPA)',
            'distance_km': '1.85',
            'travel_time': '6 min by auto',
            'directions_note': 'Updated directions note',
            'display_order': 2,
        })
        self.assertRedirects(res_edit, url)
        place.refresh_from_db()
        self.assertEqual(place.name, 'Ambalapuzha Railway Station (AMPA)')
        self.assertEqual(place.distance_km, Decimal('1.85'))

        # 3. Delete
        del_url = reverse('staff_panel:website_nearby_place_delete', kwargs={'pk': place.id})
        res_del = self.client.post(del_url)
        self.assertRedirects(res_del, url)
        self.assertFalse(NearbyPlace.objects.filter(id=place.id).exists())

    def test_chatbot_faqs_crud_and_toggle(self):
        """ChatFAQ creation, editing, active toggle, and deletion."""
        self.client.login(username='staff_web', password='Password123!')
        url = reverse('staff_panel:website_faqs')

        # 1. Create FAQ
        res_create = self.client.post(url, {
            'action': 'create',
            'question': 'Is hot water available 24 hours?',
            'keywords': 'hot water, geyser, chooduvellam, 24 hours',
            'answer': 'Yes, centralized hot water is available 24/7 in all rooms.',
            'is_active': True,
            'display_order': 1,
        })
        self.assertRedirects(res_create, url)
        faq = ChatFAQ.objects.get(question='Is hot water available 24 hours?')
        self.assertTrue(faq.is_active)

        # 2. Toggle active
        toggle_url = reverse('staff_panel:website_faq_toggle', kwargs={'pk': faq.id})
        res_toggle = self.client.post(toggle_url)
        self.assertRedirects(res_toggle, url)
        faq.refresh_from_db()
        self.assertFalse(faq.is_active)

        # Toggle back to active
        self.client.post(toggle_url)
        faq.refresh_from_db()
        self.assertTrue(faq.is_active)

        # 3. Edit FAQ
        res_edit = self.client.post(url, {
            'action': 'edit',
            'faq_id': faq.id,
            'question': 'Is 24-hour hot water available?',
            'keywords': 'hot water, geyser, chooduvellam',
            'answer': 'Yes, solar and electrical hot water is provided round the clock.',
            'is_active': True,
            'display_order': 1,
        })
        self.assertRedirects(res_edit, url)
        faq.refresh_from_db()
        self.assertEqual(faq.question, 'Is 24-hour hot water available?')

        # 4. Delete FAQ
        del_url = reverse('staff_panel:website_faq_delete', kwargs={'pk': faq.id})
        res_del = self.client.post(del_url)
        self.assertRedirects(res_del, url)
        self.assertFalse(ChatFAQ.objects.filter(id=faq.id).exists())

    def test_unanswered_questions_workflow(self):
        """Unanswered questions listing, mark handled, delete, and create FAQ flow."""
        self.client.login(username='staff_web', password='Password123!')

        q1 = UnansweredQuestion.objects.create(text="Do you have an electric vehicle charging station?", count=3)
        q2 = UnansweredQuestion.objects.create(text="What is the driver accommodation fee?", count=1)

        list_url = reverse('staff_panel:website_unanswered_questions')
        res = self.client.get(list_url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "electric vehicle charging station")
        self.assertContains(res, "driver accommodation fee")

        # Mark handled
        handle_url = reverse('staff_panel:website_unanswered_handle', kwargs={'pk': q1.id})
        self.client.post(handle_url)
        q1.refresh_from_db()
        self.assertTrue(q1.is_handled)

        # Test prefilled FAQ creation from unanswered question
        faq_create_url = reverse('staff_panel:website_faqs')
        prefill_res = self.client.get(f"{faq_create_url}?prefill_question={q2.text}&from_unanswered_id={q2.id}")
        self.assertEqual(prefill_res.status_code, 200)
        self.assertContains(prefill_res, q2.text)

        # Submit FAQ with from_unanswered_id
        res_faq_create = self.client.post(faq_create_url, {
            'action': 'create',
            'from_unanswered_id': q2.id,
            'question': q2.text,
            'keywords': 'driver, accommodation, driver room',
            'answer': 'Driver dormitory beds are available at a nominal rate.',
            'is_active': True,
            'display_order': 1,
        })
        self.assertRedirects(res_faq_create, faq_create_url)
        q2.refresh_from_db()
        self.assertTrue(q2.is_handled)

        # Delete unanswered question
        del_url = reverse('staff_panel:website_unanswered_delete', kwargs={'pk': q1.id})
        self.client.post(del_url)
        self.assertFalse(UnansweredQuestion.objects.filter(id=q1.id).exists())

