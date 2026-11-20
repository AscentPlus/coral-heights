from django.test import TestCase


class HomePageHeroVideoTestCase(TestCase):
    """Tests for the hero section video replacement."""

    def test_home_page_renders_video_element(self):
        """The home page contains a <video> element with required attributes."""
        import re
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('<video', content)
        self.assertIn('muted', content)
        self.assertIn('loop', content)
        self.assertIn('playsinline', content)
        video_tag = content.split('<video')[1].split('>')[0]
        # Ensure 'controls' attribute is not present (controlslist is allowed)
        self.assertIsNone(re.search(r'\bcontrols\b(?!list)', video_tag))

    def test_hero_has_sr_only_h1(self):
        """The hero section has a visually hidden <h1> for SEO and accessibility."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('sr-only', content)
        self.assertIn('Hotel Coral Heights', content)
        # Verify the h1 tag has sr-only class
        self.assertIn('<h1 class="sr-only">', content)

    def test_old_hero_text_removed(self):
        """The old hero text content is no longer present."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertNotIn('Feel Happy', content)
        self.assertNotIn('Feel Safe', content)
        self.assertNotIn('At the Heights', content)
        self.assertNotIn('Hospitality combines with modern luxury', content)
        # The "Ambalapuzha · Alappuzha · Kerala" eyebrow line should be gone
        self.assertNotIn('Ambalapuzha · Alappuzha · Kerala', content)

    def test_hero_video_has_poster(self):
        """The video element references a poster image."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('hero-poster.jpg', content)

    def test_hero_section_uses_alpine_component(self):
        """The hero section uses the heroVideo Alpine component."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('x-data="heroVideo"', content)

    def test_availability_widget_still_present(self):
        """The availability widget section exists and is bound to availabilityWidget."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('id="availability"', content)
        self.assertIn('availabilityWidget', content)

    def test_hero_video_ambient_presentation(self):
        """Hero video plays ambiently without intrusive controls."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('x-data="heroVideo"', content)
        self.assertNotIn('togglePlay', content)
        self.assertNotIn('toggleMute', content)

    def test_guest_essentials_outside_hero(self):
        """Verified guest essentials (check-in/out, parking, cancellation) are rendered."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('Check-in', content)
        self.assertIn('Check-out', content)
        self.assertIn('Parking', content)
        self.assertIn('Cancellation', content)


class ShareableDetailPagesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from content.models import RoomType, Attraction
        from hotel_info.models import RestaurantInfo, MenuCategory, MenuItem, NearbyPlace
        cls.room = RoomType.objects.create(
            name="Deluxe Heritage Room",
            slug="deluxe-heritage-room",
            base_price_per_night=3500.00,
            max_occupancy=3,
            short_description="Spacious heritage room."
        )
        cls.restaurant = RestaurantInfo.objects.create(
            name="The Pepper Tree",
            cuisine_description="Authentic Kerala cuisine",
            breakfast_hours="7:30 AM – 10:00 AM",
            dinner_hours="7:30 PM – 10:30 PM"
        )
        cls.cat = MenuCategory.objects.create(name="Kerala Delicacies", display_order=1)
        cls.item = MenuItem.objects.create(
            category=cls.cat,
            name="Karimeen Pollichathu",
            price=450.00,
            is_veg=False,
            is_available=True
        )
        cls.station = NearbyPlace.objects.create(
            place_type="railway_station",
            name="Ambalapuzha Railway Station",
            distance_km=0.75,
            travel_time="2 min by auto"
        )
        cls.attraction = Attraction.objects.create(
            name="Sree Krishna Temple",
            description="Ancient temple famous for Palpayasam.",
            distance_label="1.5 km",
            display_order=1
        )

    def test_room_detail_page_renders_verified_info(self):
        response = self.client.get(f'/rooms/{self.room.slug}/?check_in=2026-12-01&check_out=2026-12-03&adults=2')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Deluxe Heritage Room", content)
        self.assertIn("3 Guests", content)
        self.assertIn("₹3500", content)
        # Check booking button preserves query parameters
        self.assertIn("check_in=2026-12-01", content)
        self.assertIn("check_out=2026-12-03", content)
        self.assertIn("adults=2", content)

    def test_dining_page_renders_hours_and_menu(self):
        response = self.client.get('/dining/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("The Pepper Tree", content)
        self.assertIn("7:30 AM – 10:00 AM", content)
        self.assertIn("Karimeen Pollichathu", content)
        self.assertIn("₹450", content)
        self.assertIn("Dietary &amp; Food Allergy Note", content)

    def test_events_navigation_and_redirect(self):
        """Events in navbar links directly to home event section, and /events/ redirects there."""
        home_resp = self.client.get('/')
        self.assertEqual(home_resp.status_code, 200)
        home_content = home_resp.content.decode()
        self.assertIn('#events', home_content)
        self.assertIn('id="events"', home_content)
        self.assertIn("Plan Your Event", home_content)
        self.assertIn("id_contact_phone", home_content)

        # Legacy URL redirect to homepage section
        events_resp = self.client.get('/events/')
        self.assertRedirects(events_resp, '/#events', status_code=302, target_status_code=200)

    def test_location_page_renders_transit_and_address(self):
        response = self.client.get('/location/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Location &amp; How to Reach", content)
        self.assertIn("Ambalapuzha Railway Station", content)
        self.assertIn("0.75 km", content)
        self.assertIn("Sree Krishna Temple", content)
        self.assertIn("1.5 km", content)
        self.assertIn('class="bg-watermark subpage"', content)

    def test_sitemap_xml(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        content = response.content.decode()
        self.assertIn('<urlset', content)
        self.assertIn('/rooms/deluxe-heritage-room/', content)
        self.assertIn('/dining/', content)
        self.assertIn('/location/', content)


