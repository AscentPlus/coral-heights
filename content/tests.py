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
        """The availability widget section still exists and overlaps the hero."""
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('id="availability"', content)
        self.assertIn('-mt-20', content)
        self.assertIn('availabilityWidget', content)

