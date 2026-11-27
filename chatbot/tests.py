import json
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from django.core.management import call_command
from io import StringIO

from content.models import RoomType, Facility, Attraction, ContactInformation
from hotel_info.models import (
    HotelInfo, RestaurantInfo, MenuCategory, MenuItem,
    NearbyPlace, ChatFAQ, UnansweredQuestion
)
from bookings.constants import CANCELLATION_POLICY
from chatbot.engine import answer


class ChatbotEngineTableDrivenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. Contact info
        cls.contact = ContactInformation.objects.create(
            primary_phone='+91 9496200777',
            whatsapp_number='+919496200777',
            email='info@coralheights.com',
            address_line_1='Hotel Coral Heights',
            address_line_2='Ambalapuzha, Alappuzha',
            address_line_3='Kerala — 688 561'
        )

        # 2. Hotel info
        cls.hotel_info = HotelInfo.objects.create(
            check_in_time="12:00 PM",
            check_out_time="11:00 AM",
            address_note="Located directly on NH 66, right opposite the Ambalapuzha Temple Junction.",
            parking_info="Free valet parking on-site for all staying guests.",
            wifi_info="High-speed optical Wi-Fi available throughout the hotel.",
            payment_methods="Cash, UPI (Google Pay, PhonePe), and major Credit/Debit Cards.",
            languages_spoken="Malayalam, English, Hindi, and Tamil.",
            pet_policy="Pets are not allowed on the property.",
            rate_note="Rates vary by date and meal plan. Use the Check Availability box for the exact price."
        )

        # 3. Restaurant info
        cls.restaurant_info = RestaurantInfo.objects.create(
            name="Coral Dining Hall",
            cuisine_description="Authentic Kuttanad and coastal Kerala specialties, plus North and South Indian favorites.",
            breakfast_hours="7:30 AM – 10:30 AM",
            lunch_hours="12:30 PM – 3:30 PM",
            dinner_hours="7:30 PM – 10:30 PM",
            thattukada_hours="4:30 PM – 8:30 PM",
            room_service_info="Available 24 hours for beverages and light snacks."
        )

        # 4. Room Types
        cls.deluxe_room = RoomType.objects.create(
            name="Deluxe Room",
            slug="deluxe-room",
            short_description="Spacious room with modern amenities and pool view.",
            base_price_per_night=Decimal("2800.00"),
            max_occupancy=2,
            bed_type="King Bed",
            display_order=1
        )
        cls.executive_suite = RoomType.objects.create(
            name="Executive Suite",
            slug="executive-suite",
            short_description="Luxury suite with separate living area and jacuzzi.",
            base_price_per_night=Decimal("4500.00"),
            max_occupancy=3,
            bed_type="King Bed",
            display_order=2
        )

        # 5. Facilities
        cls.facility_pool = Facility.objects.create(name="Swimming Pool", display_order=1)
        cls.facility_wifi = Facility.objects.create(name="Free High-Speed Wi-Fi", display_order=2)
        cls.facility_gen = Facility.objects.create(name="24-Hour Generator Power Backup", display_order=3)

        # 6. Menu
        cls.cat_kerala = MenuCategory.objects.create(name="Kerala Delicacies", display_order=1)
        cls.cat_veg = MenuCategory.objects.create(name="Vegetarian Meals", display_order=2)

        cls.item_fish = MenuItem.objects.create(
            category=cls.cat_kerala,
            name="Karimeen Pollichathu",
            description="Pearl spot fish baked in banana leaf with shallots and spices",
            price=Decimal("380.00"),
            is_veg=False,
            is_available=True,
            display_order=1
        )
        cls.item_biryani = MenuItem.objects.create(
            category=cls.cat_kerala,
            name="Thalassery Chicken Biryani",
            description="Fragrant kaima rice dum biryani with Malabar spices",
            price=Decimal("260.00"),
            is_veg=False,
            is_available=True,
            display_order=2
        )
        cls.item_veg_stew = MenuItem.objects.create(
            category=cls.cat_veg,
            name="Vegetable Stew with Appam",
            description="Mild coconut milk stew with garden vegetables",
            price=Decimal("160.00"),
            is_veg=True,
            is_available=True,
            display_order=3
        )
        cls.item_crab = MenuItem.objects.create(
            category=cls.cat_kerala,
            name="Mud Crab Roast",
            description="Crab in black pepper and coconut masala",
            price=Decimal("480.00"),
            is_veg=False,
            is_available=False,  # Unavailable test
            display_order=4
        )

        # 7. Nearby Places
        cls.place_station = NearbyPlace.objects.create(
            place_type="railway_station",
            name="Ambalapuzha Railway Station",
            distance_km=Decimal("1.80"),
            travel_time="5 min by auto",
            directions_note="Head north on NH 66 towards station road."
        )
        cls.place_bus = NearbyPlace.objects.create(
            place_type="bus_stand",
            name="Ambalapuzha KSRTC Bus Stand",
            distance_km=Decimal("0.80"),
            travel_time="2 min walk / auto",
            directions_note="Located right on the main highway."
        )
        cls.place_airport = NearbyPlace.objects.create(
            place_type="airport",
            name="Cochin International Airport (COK)",
            distance_km=Decimal("98.00"),
            travel_time="2.5 hours by taxi",
            directions_note="Take NH 66 North via Alappuzha bypass."
        )
        cls.place_hospital = NearbyPlace.objects.create(
            place_type="hospital",
            name="Surya Hospital",
            distance_km=Decimal("0.20"),
            travel_time="1 min",
            directions_note="Near bus stand."
        )

        # 8. Attractions
        cls.attraction_temple = Attraction.objects.create(
            name="Ambalapuzha Sri Krishna Temple",
            description="Famous historic temple renowned for its traditional Palpayasam sweet offering.",
            distance_label="1.2 km",
            display_order=1
        )
        cls.attraction_beach = Attraction.objects.create(
            name="Alappuzha Beach & Pier",
            description="Famous golden sandy beach with historic sea bridge pier.",
            distance_label="14.0 km",
            display_order=2
        )

        # 9. Active FAQ
        cls.faq_hot_water = ChatFAQ.objects.create(
            question="Is hot water available in the bathrooms?",
            keywords="hot water, geyser, chooduvellam, 24 hours hot water",
            answer="Yes, 24-hour centralized solar and electric hot water is available in every room bathroom.",
            is_active=True,
            display_order=1
        )

    def test_table_driven_40_plus_questions(self):
        """
        Table-driven test suite with at least 55 sample questions covering:
        - English standard questions
        - Typos and misspellings
        - Malayalam / Manglish queries
        - Checking that expected content strings appear in the answer.
        """
        test_cases = [
            # Rooms & Rates (English, Typos, Manglish)
            ("What are the room rates?", "from ₹2800.00 per night"),
            ("How much does a room cost per night?", "from ₹2800.00"),
            ("What is the tariff for rooms?", "Executive Suite"),
            ("Tell me about the deluxe room rate", "Deluxe Room"),
            ("What is the price of Executive Suite?", "Executive Suite"),
            ("how much for delux room", "Deluxe Room"),  # typo
            ("room rent ethraya", "from ₹"),  # Manglish
            ("muri vaadaka ethra", "from ₹"),  # Malayalam script
            ("suite room tariff", "Executive Suite"),

            # Facilities (English, Typos, Manglish)
            ("What facilities do you have?", "Swimming Pool"),
            ("Is there a swimming pool?", "Swimming Pool"),
            ("Do you have free wifi?", "High-speed optical Wi-Fi"),
            ("What are your parking facilities?", "Free valet parking"),
            ("Is power backup available?", "Generator Power Backup"),
            ("hotelil parking undo", "Parking:"),  # Manglish
            ("swimming pul undo", "Swimming Pool"),  # Manglish typo
            ("facilties details", "Swimming Pool"),  # Typo

            # Restaurant & Food (English, Typos, Manglish, Dishes)
            ("What are the restaurant dining hours?", "Breakfast: 7:30 AM"),
            ("What time is breakfast served?", "7:30 AM – 10:30 AM"),
            ("What are your dinner hours?", "Dinner: 7:30 PM"),
            ("What time is thattukada open?", "4:30 PM – 8:30 PM"),
            ("Do you have vegetarian food?", "Vegetable Stew with Appam"),
            ("pure veg options", "Vegetable Stew with Appam"),
            ("Is biryani available on the menu?", "Thalassery Chicken Biryani"),
            ("Do you have Karimeen Pollichathu?", "Karimeen Pollichathu"),
            ("Do you have Mud Crab Roast?", "currently listed as unavailable"),
            ("bhakshanam samayam epozha", "Breakfast: 7:30 AM"),  # Manglish
            ("resturant menu", "Coral Dining Hall"),  # Typo
            ("chaya and thattukada", "4:30 PM – 8:30 PM"),  # Manglish

            # How to reach / Transport (English, Typos, Manglish)
            ("How to reach the hotel?", "Ambalapuzha Railway Station"),
            ("How far is the railway station?", "1.80 km away"),
            ("Distance to the bus stand", "0.80 km"),
            ("How far is Cochin airport?", "98.00 km"),
            ("railway station ethan ethra samayam edukum", "1.80 km away"),  # Manglish
            ("station vazhi parayamo", "1.80 km away"),  # Manglish
            ("distence to train station", "1.80 km away"),  # Typo

            # Attractions (English, Typos, Manglish)
            ("What are the nearby tourist attractions?", "Ambalapuzha Sri Krishna Temple"),
            ("How far is Ambalapuzha Temple?", "Ambalapuzha Sri Krishna Temple"),
            ("Places to visit near the hotel", "Alappuzha Beach & Pier"),
            ("sight seeing spots nearby", "Ambalapuzha Sri Krishna Temple"),  # Typo
            ("kaanenda sthalangal", "Ambalapuzha Sri Krishna Temple"),  # Malayalam

            # Hotel info (check-in/out, pets, payment, languages)
            ("What is your check in time?", "Check-in: 12:00 PM"),
            ("What time is check out?", "Check-out: 11:00 AM"),
            ("Are pets allowed in the hotel?", "Pets are not allowed"),
            ("What payment methods do you accept?", "UPI (Google Pay, PhonePe)"),
            ("Can I pay using Google Pay or card?", "UPI (Google Pay, PhonePe)"),
            ("What languages do the staff speak?", "Malayalam, English, Hindi"),
            ("checkin samayam epozha", "Check-in: 12:00 PM"),  # Manglish

            # Contact and location
            ("What is your contact phone number?", "+91 9496200777"),
            ("Can I chat on WhatsApp?", "+919496200777"),
            ("What is the hotel address?", "Ambalapuzha, Alappuzha"),
            ("Where are you located?", "Hotel Coral Heights"),

            # Cancellation & Refund
            ("What is your cancellation policy?", "Cancellation and refund requests must be made"),
            ("Can I get a refund if I cancel my booking?", "24 hours before your scheduled check-in"),

            # Availability & Booking (Must NEVER promise availability)
            ("Is a room free tomorrow?", "Check Availability box"),
            ("Can I book a room for next Friday?", "Check Availability box"),
            ("Check room availability", "Check Availability box"),

            # Events & Catering
            ("Can I host a wedding reception here?", "banquet"),
            ("Do you provide catering for birthday parties?", "catering"),
            ("Is banquet hall available for meeting?", "banquet"),
        ]

        self.assertGreaterEqual(len(test_cases), 55)

        for query, expected_substring in test_cases:
            with self.subTest(query=query):
                res = answer(query)
                self.assertTrue(res["matched"], f"Query '{query}' was expected to match, but matched=False")
                self.assertIn(
                    expected_substring.lower(),
                    res["answer"].lower(),
                    f"Expected '{expected_substring}' in answer for query '{query}'. Got: {res['answer']}"
                )
                # Verify whitelisted action types
                for act in res.get("actions", []):
                    self.assertIn(act["type"], ["scroll", "tel", "whatsapp", "topic"])
                    self.assertTrue(bool(act.get("label")))
                    self.assertTrue(bool(act.get("value")))

    def test_faq_override_generic_topic(self):
        """Staff-entered ChatFAQ overrides default answer when its keywords match."""
        res = answer("Do you have hot water in the room?")
        self.assertTrue(res["matched"])
        self.assertIn("solar and electric hot water is available in every room", res["answer"].lower())

    def test_dish_not_on_menu(self):
        """Querying for a dish not on the menu offers restaurant info without hallucinating."""
        res = answer("Do you have Sushi?")
        # Sushi is not on menu, so it falls back to restaurant overview or general query without saying sushi is served
        self.assertNotIn("sushi is on our menu", res["answer"].lower())

    def test_single_room_query_focuses_on_that_room(self):
        """Query specifying Deluxe Room answers for Deluxe Room only."""
        res = answer("What is the deluxe room rate?")
        self.assertTrue(res["matched"])
        self.assertIn("deluxe room", res["answer"].lower())
        self.assertNotIn("executive suite", res["answer"].lower())

    def test_empty_database_fallback(self):
        """When a topic has no database entries, states so plainly and provides phone."""
        # Test with empty Attractions
        Attraction.objects.all().delete()
        res = answer("What are nearby attractions?")
        self.assertTrue(res["matched"])
        self.assertIn("have not been entered", res["answer"].lower())
        self.assertIn(self.contact.primary_phone, res["answer"])

    def test_tie_breaker_clarification_buttons(self):
        """When two topics tie, engine returns a clarifying question with action buttons."""
        # Construct an artificial query that touches both topics equally
        res = answer("room restaurant")
        self.assertTrue(res["matched"])
        # Should ask whether user wants room or restaurant info
        self.assertTrue(
            "would you like information about" in res["answer"].lower() or
            len([a for a in res["actions"] if a["type"] == "topic"]) >= 2
        )

    def test_how_to_reach_excludes_hospitals_and_shows_landmark(self):
        """
        When asking general how to reach, do not show hospitals, ATMs or other categories;
        only show railway station, bus stand and the landmark note.
        """
        res = answer("How to reach the hotel?")
        self.assertTrue(res["matched"])
        self.assertIn("ambalapuzha railway station", res["answer"].lower())
        self.assertIn("ambalapuzha ksrtc bus stand", res["answer"].lower())
        self.assertIn("landmark:", res["answer"].lower())
        self.assertIn("located directly on nh 66", res["answer"].lower())
        # Hospital must NOT appear in general how to reach
        self.assertNotIn("surya hospital", res["answer"].lower())


class ChatbotEndpointAndAbuseTests(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()
        self.contact = ContactInformation.objects.create(
            primary_phone='+91 9496200777',
            whatsapp_number='+919496200777'
        )

    def test_chat_ask_valid_request(self):
        """POST /chat/ask/ with valid JSON returns 200 and expected schema."""
        url = reverse('chatbot:ask')
        res = self.client.post(
            url,
            data=json.dumps({"message": "What is the check-in time?"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("answer", data)
        self.assertIn("actions", data)
        self.assertIn("matched", data)
        self.assertTrue(data["matched"])

    def test_chat_topics_endpoint(self):
        """GET /chat/topics/ returns 200 and list of quick-reply topics."""
        url = reverse('chatbot:topics')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("topics", data)
        self.assertGreaterEqual(len(data["topics"]), 4)

    def test_reject_empty_message(self):
        """Empty or whitespace-only message returns HTTP 400."""
        url = reverse('chatbot:ask')
        res = self.client.post(
            url,
            data=json.dumps({"message": "   "}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot be empty", res.json().get("error", ""))

    def test_reject_over_300_chars(self):
        """Message exceeding 300 characters returns HTTP 400."""
        url = reverse('chatbot:ask')
        long_msg = "hello " * 65  # > 300 chars
        res = self.client.post(
            url,
            data=json.dumps({"message": long_msg}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceeds the 300-character limit", res.json().get("error", ""))

    def test_reject_bad_json(self):
        """Malformed JSON payload returns HTTP 400."""
        url = reverse('chatbot:ask')
        res = self.client.post(
            url,
            data="not a json {",
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid JSON", res.json().get("error", ""))

    def test_rate_limiting_429(self):
        """Sending more than 20 messages in 10 minutes returns HTTP 429."""
        url = reverse('chatbot:ask')
        for i in range(20):
            res = self.client.post(
                url,
                data=json.dumps({"message": f"Hello {i}"}),
                content_type="application/json"
            )
            self.assertEqual(res.status_code, 200)

        # 21st message must be rate-limited
        res_limit = self.client.post(
            url,
            data=json.dumps({"message": "Hello 21"}),
            content_type="application/json"
        )
        self.assertEqual(res_limit.status_code, 429)
        self.assertIn("quite a few messages", res_limit.json().get("error", ""))

    def test_xss_safety_html_never_executed(self):
        """Malicious script tags in user question are sanitized and treated as literal text."""
        url = reverse('chatbot:ask')
        script_payload = "<script>alert('xss')</script> does hotel have pool?"
        res = self.client.post(
            url,
            data=json.dumps({"message": script_payload}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Answer must not execute script or reflect dangerous unescaped tags
        self.assertNotIn("<script>", data["answer"])


class UnansweredQuestionDedupeAndPurgeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.contact = ContactInformation.objects.create(
            primary_phone='+91 9496200777',
            whatsapp_number='+919496200777'
        )

    def test_unanswered_question_deduplication(self):
        """Asking the same unknown question multiple times increments count instead of inserting duplicates."""
        initial_count = UnansweredQuestion.objects.count()

        q_text = "What is the policy for drone flying?"
        res1 = answer(q_text)
        self.assertFalse(res1["matched"])
        self.assertEqual(UnansweredQuestion.objects.count(), initial_count + 1)

        uq = UnansweredQuestion.objects.get(text=q_text)
        self.assertEqual(uq.count, 1)

        # Ask again
        res2 = answer(q_text)
        self.assertFalse(res2["matched"])
        self.assertEqual(UnansweredQuestion.objects.count(), initial_count + 1)

        uq.refresh_from_db()
        self.assertEqual(uq.count, 2)

    def test_purge_unanswered_management_command(self):
        """purge_unanswered deletes handled questions older than threshold, preserving unhandled or recent ones."""
        now = timezone.now()
        old_date = now - timedelta(days=95)
        recent_date = now - timedelta(days=10)

        # 1. Old handled -> MUST BE PURGED
        q_old_handled = UnansweredQuestion.objects.create(
            text="Old handled question", count=1, is_handled=True
        )
        UnansweredQuestion.objects.filter(id=q_old_handled.id).update(last_asked=old_date)

        # 2. Old unhandled -> MUST BE KEPT (staff still needs to review)
        q_old_unhandled = UnansweredQuestion.objects.create(
            text="Old unhandled question", count=1, is_handled=False
        )
        UnansweredQuestion.objects.filter(id=q_old_unhandled.id).update(last_asked=old_date)

        # 3. Recent handled -> MUST BE KEPT (< 90 days)
        q_recent_handled = UnansweredQuestion.objects.create(
            text="Recent handled question", count=1, is_handled=True
        )
        UnansweredQuestion.objects.filter(id=q_recent_handled.id).update(last_asked=recent_date)

        # Run management command
        out = StringIO()
        call_command('purge_unanswered', '--days=90', stdout=out)
        output_str = out.getvalue()
        self.assertIn("Successfully purged 1 handled question", output_str)

        # Verify DB state
        self.assertFalse(UnansweredQuestion.objects.filter(id=q_old_handled.id).exists())
        self.assertTrue(UnansweredQuestion.objects.filter(id=q_old_unhandled.id).exists())
        self.assertTrue(UnansweredQuestion.objects.filter(id=q_recent_handled.id).exists())


class ChatbotAuditRegressionTests(TestCase):
    """
    Regression test suite specifically verifying the 11 audit prompts, stable intent IDs,
    JSON object body validation, allergen neutrality, and PII redaction.
    """
    @classmethod
    def setUpTestData(cls):
        cls.contact = ContactInformation.objects.create(
            primary_phone='+91 9496200777',
            whatsapp_number='+919496200777',
            email='info@coralheights.com',
            address_line_1='Hotel Coral Heights',
            address_line_2='Temple Road, Ambalapuzha',
            address_line_3='Alappuzha, Kerala — 688 561'
        )

        cls.hotel_info = HotelInfo.objects.create(
            check_in_time="12:00 PM",
            check_out_time="11:00 AM",
            address_note="Located 350 meters east of NH 66 Ambalapuzha Junction.",
            parking_info="On-site guest parking available.",
            wifi_info="High-speed optical Wi-Fi available.",
            payment_methods="Cash, UPI, Credit/Debit cards accepted.",
            languages_spoken="Malayalam, English, Hindi",
            pet_policy="Pets are not allowed on the property.",
            rate_note="Rates vary by date and meal plan. Use the Check Availability option for the exact price."
        )

        cls.restaurant_info = RestaurantInfo.objects.create(
            name="Coral Heights Restaurant",
            cuisine_description="Traditional Kerala Cuisine and North Indian Specialties",
            breakfast_hours="8:00 AM to 11:00 AM",
            lunch_hours="12:30 PM to 3:30 PM",
            dinner_hours="7:30 PM to 10:30 PM",
            thattukada_hours="5:00 PM to 9:00 PM",
            room_service_info="Room service available from 7:00 AM to 11:00 PM",
        )

        cls.cat_kerala = MenuCategory.objects.create(name="Kerala Specials", display_order=1)
        cls.item_karimeen = MenuItem.objects.create(
            category=cls.cat_kerala,
            name="Karimeen Pollichathu",
            description="Pearl spot fish coated in spicy masala wrapped in banana leaf and roasted.",
            price=None,  # Price is unconfigured initially
            is_veg=False,
            is_available=True,
            display_order=1
        )

        cls.fac_wheelchair = Facility.objects.create(
            name="Wheelchair Accessibility",
            display_order=1
        )

        cls.room_deluxe = RoomType.objects.create(
            name="Deluxe Suite",
            slug="deluxe-suite",
            base_price_per_night=Decimal('4500.00'),
            max_occupancy=3,
            bed_type="King Bed",
            short_description="Spacious heritage-themed suite."
        )

        cls.faq_hot_water = ChatFAQ.objects.create(
            question="Is hot water available?",
            keywords="hot water, geyser",
            answer="Yes, all rooms are equipped with 24/7 hot water.",
            is_active=True,
            display_order=1
        )

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_json_request_body_validation(self):
        """API must reject non-object JSON shapes, empty messages and invalid types with HTTP 400."""
        url = reverse('chatbot:ask')

        # Array instead of object
        res = self.client.post(url, data=json.dumps(["hello"]), content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("JSON object", res.json()["error"])

        # String instead of object
        res = self.client.post(url, data=json.dumps("hello"), content_type="application/json")
        self.assertEqual(res.status_code, 400)

        # Empty message
        res = self.client.post(url, data=json.dumps({"message": "   "}), content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json()["error"].lower())

        # Exceeds character limit
        res = self.client.post(url, data=json.dumps({"message": "x" * 305}), content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("limit", res.json()["error"].lower())

    def test_shipped_quick_replies_and_stable_intent_ids(self):
        """Quick reply chips must have stable intent IDs and direct button actions must work."""
        url_topics = reverse('chatbot:topics')
        res = self.client.get(url_topics)
        self.assertEqual(res.status_code, 200)
        topics = res.json()["topics"]
        self.assertTrue(len(topics) >= 5)

        intent_ids = [t.get("intent_id") for t in topics]
        self.assertIn("hotel_info", intent_ids)
        self.assertIn("rooms_rates", intent_ids)
        self.assertIn("restaurant", intent_ids)

        url_ask = reverse('chatbot:ask')
        # Explicit intent action for Check-in & Policies
        res_intent = self.client.post(
            url_ask,
            data=json.dumps({"intent_id": "hotel_info"}),
            content_type="application/json"
        )
        self.assertEqual(res_intent.status_code, 200)
        data = res_intent.json()
        self.assertTrue(data["matched"])
        self.assertIn(self.hotel_info.check_in_time, data["answer"])
        self.assertIn(self.hotel_info.check_out_time, data["answer"])

    def test_prompt_1_breakfast_hours(self):
        """Prompt: 'What time do you serve breakfast?' -> leads with configured breakfast time."""
        res = answer("What time do you serve breakfast?")
        self.assertTrue(res["matched"])
        self.assertIn(self.restaurant_info.breakfast_hours, res["answer"])
        self.assertTrue(res["answer"].lower().startswith("breakfast:"))

    def test_prompt_2_cancel_booking(self):
        """Prompt: 'Can I cancel my booking?' -> shows cancellation policy & contact."""
        res = answer("Can I cancel my booking?")
        self.assertTrue(res["matched"])
        self.assertIn(CANCELLATION_POLICY[:40], res["answer"])
        self.assertIn(self.contact.primary_phone, res["answer"])

    def test_prompt_3_tokyo_weather_no_fuzzy_match(self):
        """Prompt: 'What is the weather in Tokyo?' -> must NOT fuzzy match hot water FAQ."""
        res = answer("What is the weather in Tokyo?")
        self.assertFalse(res["matched"])
        self.assertNotIn("hot water", res["answer"].lower())
        self.assertIn(self.contact.primary_phone, res["answer"])

    def test_prompt_4_dish_price_karimeen(self):
        """Prompt: 'How much is Karimeen Pollichathu?' -> states staff confirmation when price unconfigured, quotes price when set."""
        res = answer("How much is Karimeen Pollichathu?")
        self.assertTrue(res["matched"])
        self.assertIn("Karimeen Pollichathu", res["answer"])
        self.assertIn("staff can confirm", res["answer"].lower())

        # Now configure a price and verify it quotes the exact tariff
        self.item_karimeen.price = Decimal("480.00")
        self.item_karimeen.save()

        res_priced = answer("How much is Karimeen Pollichathu?")
        self.assertTrue(res_priced["matched"])
        self.assertIn("480.00", res_priced["answer"])

    def test_prompt_5_dish_allergen_neutrality(self):
        """Prompt: 'Is Karimeen Pollichathu safe for a nut allergy?' -> neutral disclaimer, no 'Yes', no safety claims."""
        res = answer("Is Karimeen Pollichathu safe for a nut allergy?")
        self.assertTrue(res["matched"])
        self.assertIn("Our restaurant team can confirm ingredients and possible cross-contact", res["answer"])
        self.assertFalse(res["answer"].strip().startswith("Yes"))
        self.assertNotIn("safe", res["answer"].lower().split())

    def test_prompt_6_wheelchair_accessible_rooms(self):
        """Prompt: 'Do you have wheelchair-accessible rooms?' -> gives exact configured info or staff contact."""
        res = answer("Do you have wheelchair-accessible rooms?")
        self.assertTrue(res["matched"])
        self.assertIn("Wheelchair Accessibility", res["answer"])
        self.assertIn(self.contact.primary_phone, res["answer"])

    def test_prompt_7_elevator_facility(self):
        """Prompt: 'Is there an elevator?' -> honest answer without making unsupported claims."""
        res = answer("Is there an elevator?")
        self.assertTrue(res["matched"])
        self.assertIn("Elevator", res["answer"])
        self.assertIn("not listed in our standard facility records", res["answer"])
        self.assertIn(self.contact.primary_phone, res["answer"])

    def test_prompt_8_hotel_location_address(self):
        """Prompt: 'Where is Hotel Coral Heights in Ambalapuzha?' -> gives address and landmark."""
        res = answer("Where is Hotel Coral Heights in Ambalapuzha?")
        self.assertTrue(res["matched"])
        self.assertIn(self.contact.address_line_1, res["answer"])
        self.assertIn(self.hotel_info.address_note, res["answer"])

    def test_prompt_9_malayalam_checkin_timing(self):
        """Prompt: 'എപ്പോഴാണ് ചെക്ക് ഇൻ?' -> answers check-in timing in Malayalam."""
        res = answer("എപ്പോഴാണ് ചെക്ക് ഇൻ?")
        self.assertTrue(res["matched"])
        self.assertIn(self.hotel_info.check_in_time, res["answer"])
        self.assertIn(self.hotel_info.check_out_time, res["answer"])

    def test_prompt_10_malayalam_room_rates(self):
        """Prompt: 'മുറിയുടെ നിരക്ക് എത്രയാണ്?' -> answers room rates in Malayalam."""
        res = answer("മുറിയുടെ നിരക്ക് എത്രയാണ്?")
        self.assertTrue(res["matched"])
        self.assertIn("4500.00", res["answer"])
        self.assertIn(self.hotel_info.rate_note, res["answer"])

    def test_prompt_11_dual_intent_booking_and_checkin(self):
        """Prompt: 'Can I book a room for tomorrow and what are your check-in times?' -> answers both."""
        res = answer("Can I book a room for tomorrow and what are your check-in times?")
        self.assertTrue(res["matched"])
        self.assertIn(self.hotel_info.check_in_time, res["answer"])
        self.assertIn("Check Availability box", res["answer"])
        # Action chips include scroll to availability
        action_vals = [a.get("value") for a in res["actions"]]
        self.assertIn("#availability", action_vals)

    def test_pii_redaction_in_unanswered_questions(self):
        """Sensitive guest PII (phone, email, card) must be redacted before saving to UnansweredQuestion."""
        UnansweredQuestion.objects.all().delete()
        text_with_pii = (
            "Can a spaceship land on your roof? My info is 9876543210 and testguest@example.com "
            "with card 4111222233334444."
        )
        res = answer(text_with_pii, record_unanswered=True)
        self.assertFalse(res["matched"])

        logged = UnansweredQuestion.objects.first()
        self.assertIsNotNone(logged)
        self.assertNotIn("9876543210", logged.text)
        self.assertNotIn("testguest@example.com", logged.text)
        self.assertNotIn("4111222233334444", logged.text)
        self.assertIn("[REDACTED_PHONE]", logged.text)
        self.assertIn("[REDACTED_EMAIL]", logged.text)
        self.assertIn("[REDACTED_CARD]", logged.text)

    def test_single_keyword_faq_matching(self):
        """Explicit single-keyword triggers on ChatFAQ must match even when phrased differently."""
        ChatFAQ.objects.create(
            question="Does the hotel have a bar?",
            keywords="bar, alcohol, liquor",
            answer="No, there is no bar on the premises.",
            is_active=True,
            display_order=2,
        )
        ChatFAQ.objects.create(
            question="Is swimming pool available?",
            keywords="swimming, pool",
            answer="No, swimming pool facilities are not available at our hotel.",
            is_active=True,
            display_order=3,
        )

        for query in ("is liquor available", "is bar available", "do you serve beer"):
            res = answer(query)
            self.assertTrue(res["matched"], f"Expected match for '{query}'")
            self.assertIn("no bar on the premises", res["answer"].lower())

        res_pool = answer("is pool available")
        self.assertTrue(res_pool["matched"])
        self.assertIn("swimming pool facilities are not available", res_pool["answer"].lower())


