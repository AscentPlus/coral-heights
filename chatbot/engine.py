import re
import difflib
import unicodedata
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from django.db.models import Q
from bookings.constants import CANCELLATION_POLICY
from content.models import RoomType, Facility, Attraction, ContactInformation
from hotel_info.models import (
    HotelInfo, RestaurantInfo, MenuCategory, MenuItem,
    NearbyPlace, ChatFAQ, UnansweredQuestion
)

# ─── Matching Thresholds & Weights ──────────────────────────────────────────
FAQ_SCORE_THRESHOLD = 0.55
FAQ_KEYWORD_MATCH_WEIGHT = 0.60
FAQ_SIMILARITY_WEIGHT = 0.40
TOPIC_TIE_THRESHOLD = 0.05
DIFFLIB_WORD_SIMILARITY_CUTOFF = 0.82

# ─── Greeting / Farewell Lists ──────────────────────────────────────────────
GREETING_WORDS = [
    'hi', 'hello', 'hey', 'greetings', 'good morning', 'good afternoon',
    'good evening', 'namaskaram', 'namaste', 'halo', 'hai', 'helo',
    'morning', 'evening', 'vanakkam'
]

THANKS_WORDS = [
    'thank you', 'thanks', 'thank u', 'thx', 'nanni', 'valare nanni',
    'dhanyavadham', 'much appreciated', 'thanks a lot', 'thankyou'
]

GOODBYE_WORDS = [
    'bye', 'goodbye', 'good bye', 'see you', 'good night', 'goodnight',
    'tata', 'cya', 'farewell', 'see ya'
]

# ─── Built-in Topics & Keyword Lists ────────────────────────────────────────
TOPIC_BOOKING = 'booking'
TOPIC_ROOMS = 'rooms_rates'
TOPIC_FACILITIES = 'facilities'
TOPIC_RESTAURANT = 'restaurant'
TOPIC_HOW_TO_REACH = 'how_to_reach'
TOPIC_ATTRACTIONS = 'attractions'
TOPIC_HOTEL_INFO = 'hotel_info'
TOPIC_CONTACT = 'contact'
TOPIC_CANCELLATION = 'cancellation'
TOPIC_EVENTS = 'events'

TOPIC_DISPLAY_NAMES = {
    TOPIC_BOOKING: 'Room Availability & Booking',
    TOPIC_ROOMS: 'Room Categories & Tariffs',
    TOPIC_FACILITIES: 'Hotel Facilities & Amenities',
    TOPIC_RESTAURANT: 'Restaurant Timings & Menu',
    TOPIC_HOW_TO_REACH: 'How to Reach & Transport',
    TOPIC_ATTRACTIONS: 'Nearby Tourist Attractions',
    TOPIC_HOTEL_INFO: 'Check-in/out & Hotel Policies',
    TOPIC_CONTACT: 'Contact Numbers & Location',
    TOPIC_CANCELLATION: 'Cancellation & Refund Policy',
    TOPIC_EVENTS: 'Banquet & Event Catering',
}

TOPIC_KEYWORDS = {
    TOPIC_BOOKING: [
        'book', 'booking', 'reserve', 'reservation', 'availability', 'available',
        'vacant', 'vacancy', 'vacancies', 'free room', 'room free', 'is room available',
        'can i book', 'book now', 'check availability', 'need a room', 'want a room',
        'room on', 'free on', 'rooms on', 'any room', 'muri undo', 'room undo',
        'free tomorrow', 'free today', 'is a room free', 'check room availability',
        'room availability', 'rooms availability', 'book a room', 'book room'
    ],
    TOPIC_ROOMS: [
        'room', 'rooms', 'rate', 'rates', 'tariff', 'tariffs', 'price', 'prices',
        'cost', 'pricing', 'charge', 'charges', 'per night', 'suite', 'deluxe',
        'executive', 'standard', 'occupancy', 'bed', 'vaadaka', 'muri', 'rent',
        'room rate', 'room rates', 'room price', 'room tariff'
    ],
    TOPIC_FACILITIES: [
        'facility', 'facilities', 'amenity', 'amenities', 'pool', 'swimming pool',
        'swimming', 'pul', 'swim', 'gym', 'fitness', 'spa', 'wifi', 'wi-fi', 'internet',
        'parking', 'car parking', 'parking lot', 'ac', 'air conditioning', 'lift',
        'elevator', 'power backup', 'generator', 'security', 'saukaaryam', 'saukaaryangal'
    ],
    TOPIC_RESTAURANT: [
        'restaurant', 'food', 'dining', 'dine', 'breakfast', 'lunch', 'dinner',
        'thattukada', 'tea', 'coffee', 'snacks', 'menu', 'dishes', 'dish',
        'veg', 'vegetarian', 'non-veg', 'non veg', 'nonveg', 'seafood', 'fish',
        'biryani', 'biriyani', 'briyani', 'meals', 'room service', 'kitchen', 'eat',
        'bhakshanam', 'oone', 'chaya', 'kaappi', 'mess',
        'dining hours', 'restaurant hours', 'dinner hours', 'breakfast hours',
        'lunch hours', 'thattukada hours', 'room service hours',
        'bhakshanam samayam', 'food samayam', 'oone samayam'
    ],
    TOPIC_HOW_TO_REACH: [
        'how to reach', 'reach', 'direction', 'directions', 'route', 'way to',
        'railway', 'station', 'train', 'bus', 'bus stand', 'bus stop', 'ksrtc',
        'airport', 'flight', 'auto', 'autorickshaw', 'taxi', 'cab', 'drive',
        'station distance', 'airport distance', 'railway distance', 'bus stand distance',
        'how far is station', 'how far is railway', 'how far is airport', 'how far is bus stand',
        'distance to railway', 'distance to station', 'distance to airport', 'distance to bus',
        'nearby station', 'vazhi', 'ethaan', 'ethan', 'evideyaanu', 'evideya'
    ],
    TOPIC_ATTRACTIONS: [
        'attraction', 'attractions', 'sightseeing', 'sight seeing', 'places to visit',
        'tourist', 'tourism', 'visit', 'nearby places to visit', 'temple', 'beach',
        'ambalapuzha temple', 'krishna temple', 'alappuzha beach', 'beach distance',
        'backwaters', 'houseboat', 'lake', 'kaanenda sthalangal'
    ],
    TOPIC_HOTEL_INFO: [
        'check in', 'check-in', 'check out', 'check-out', 'checkin', 'checkout',
        'hotel hours', 'reception hours', 'pet policy', 'pets allowed', 'dog allowed',
        'payment', 'payments', 'payment methods', 'credit card', 'debit card',
        'upi', 'gpay', 'google pay', 'phonepe', 'cash', 'languages', 'language',
        'english', 'malayalam', 'hindi', 'checkin samayam', 'checkout samayam',
        'check in samayam', 'check out samayam'
    ],
    TOPIC_CONTACT: [
        'contact', 'phone', 'mobile', 'call', 'telephone', 'number', 'whatsapp',
        'email', 'mail', 'address', 'location', 'map', 'google map', 'where are you located',
        'where are you', 'where are', 'located', 'where located', 'front desk',
        'reception', 'reception desk', 'reach you', 'phone number', 'contact number',
        'vilikkan', 'nambur', 'landmark'
    ],
    TOPIC_CANCELLATION: [
        'cancel', 'cancellation', 'cancelling', 'refund', 'refunds', 'refundable',
        'cancel policy', 'cancellation policy', 'change date', 'money back',
        'cancel booking'
    ],
    TOPIC_EVENTS: [
        'event', 'events', 'catering', 'cater', 'wedding', 'marriage', 'engagement',
        'birthday', 'party', 'conference', 'meeting', 'hall', 'banquet', 'banquet hall',
        'auditorium', 'function', 'functions', 'kalyanam'
    ]
}


def normalize_text(text: str) -> str:
    """
    Normalizes input text without breaking Malayalam or other non-Latin scripts:
    1. Unicode NFKC normalization
    2. Lowercase
    3. Strip control characters
    4. Replace punctuation with space (preserves all Unicode letters/marks and digits)
    5. Collapse whitespace
    """
    if not text:
        return ""
    # 1. Unicode NFKC
    norm = unicodedata.normalize('NFKC', text)
    # 2. Lowercase
    norm = norm.lower()
    # 3. Strip control characters
    norm = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', norm)
    # 4. Replace punctuation and underscores with space; \w matches letters in all scripts
    norm = re.sub(r'[^\w\s]|_', ' ', norm)
    # 5. Collapse multiple spaces
    norm = re.sub(r'\s+', ' ', norm).strip()
    return norm


def _get_contact_info():
    return ContactInformation.objects.first() or ContactInformation.objects.create()


def _get_default_quick_replies() -> List[Dict[str, str]]:
    """Returns the standard quick-reply action chips."""
    contact = _get_contact_info()
    return [
        {"label": "Rooms & Rates", "type": "topic", "value": "rooms"},
        {"label": "Restaurant & Menu", "type": "topic", "value": "restaurant"},
        {"label": "Facilities", "type": "topic", "value": "facilities"},
        {"label": "How to Reach", "type": "topic", "value": "directions"},
        {"label": "Check Availability", "type": "scroll", "value": "#availability"},
        {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
    ]


def _match_keywords(normalized_query: str, keyword_list: List[str]) -> Tuple[int, float]:
    """
    Checks for exact and fuzzy keyword hits in the normalized query.
    Prevents double-counting tokens for the same topic.
    """
    if not normalized_query or not keyword_list:
        return 0, 0.0

    query_padded = f" {normalized_query} "
    query_tokens = normalized_query.split()
    matched_query_words = set()
    hits = 0

    # 1. First pass: Multi-word phrases
    for kw in keyword_list:
        kw_norm = normalize_text(kw)
        if not kw_norm or ' ' not in kw_norm:
            continue
        if f" {kw_norm} " in query_padded:
            hits += 2
            for word in kw_norm.split():
                matched_query_words.add(word)

    # 2. Second pass: Single words
    for kw in keyword_list:
        kw_norm = normalize_text(kw)
        if not kw_norm or ' ' in kw_norm:
            continue
        if kw_norm in matched_query_words:
            continue

        if f" {kw_norm} " in query_padded:
            hits += 1
            matched_query_words.add(kw_norm)
        elif len(kw_norm) >= 5:
            # Fuzzy match only for words with length >= 5
            unmatched = [t for t in query_tokens if t not in matched_query_words and len(t) >= 5]
            close = difflib.get_close_matches(
                kw_norm, unmatched, n=1, cutoff=DIFFLIB_WORD_SIMILARITY_CUTOFF
            )
            if close:
                hits += 1
                matched_query_words.add(close[0])

    score = min(1.0, hits / 2.0) if hits else 0.0
    return hits, score


def _match_chat_faqs(normalized_query: str) -> Optional[Tuple[float, ChatFAQ]]:
    """
    Matches normalized query against active ChatFAQ entries.
    Scores by keyword hits plus difflib similarity to the FAQ question.
    Returns (score, ChatFAQ) if score meets FAQ_SCORE_THRESHOLD, else None.
    """
    active_faqs = ChatFAQ.objects.filter(is_active=True).order_by('display_order', 'id')
    if not active_faqs.exists():
        return None

    best_faq = None
    best_score = 0.0
    query_tokens = normalized_query.split()

    for faq in active_faqs:
        faq_q_norm = normalize_text(faq.question)
        similarity = difflib.SequenceMatcher(None, normalized_query, faq_q_norm).ratio()

        # Keyword match
        kw_hits = 0
        if faq.keywords:
            keywords = [k.strip() for k in faq.keywords.split(',') if k.strip()]
            for kw in keywords:
                k_norm = normalize_text(kw)
                if not k_norm:
                    continue
                if ' ' in k_norm:
                    if f" {k_norm} " in f" {normalized_query} ":
                        kw_hits += 2
                else:
                    if f" {k_norm} " in f" {normalized_query} ":
                        kw_hits += 1
                    else:
                        close = difflib.get_close_matches(
                            k_norm, query_tokens, n=1, cutoff=DIFFLIB_WORD_SIMILARITY_CUTOFF
                        )
                        if close:
                            kw_hits += 1

        kw_score = min(1.0, kw_hits / 2.0) if kw_hits else 0.0

        # Direct strong keyword hit gets priority boost
        if kw_hits > 0:
            score = (FAQ_KEYWORD_MATCH_WEIGHT * kw_score) + (FAQ_SIMILARITY_WEIGHT * similarity)
            # Guarantee passing threshold if an explicit keyword hit occurred
            score = max(score, 0.70)
        else:
            # When no keywords match at all, only match if the question text itself is very similar (>= 0.82)
            score = similarity if similarity >= 0.82 else 0.0

        if score > best_score:
            best_score = score
            best_faq = faq

    if best_score >= FAQ_SCORE_THRESHOLD and best_faq:
        return best_score, best_faq

    return None


def _format_rooms_rates_answer(normalized_query: str) -> Dict[str, Any]:
    """Answers room types and tariff queries."""
    hotel_info = HotelInfo.load()
    room_types = list(RoomType.objects.all())
    contact = _get_contact_info()

    if not room_types:
        return {
            "answer": (
                f"Our room categories and tariffs have not been updated yet. "
                f"Please contact our front desk at {contact.primary_phone} or on WhatsApp for current rates."
            ),
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    # Check if a specific room type is mentioned
    specific_room = None
    query_padded = f" {normalized_query} "
    query_tokens = normalized_query.split()

    # 1. Exact full name match
    for rt in room_types:
        rt_norm = normalize_text(rt.name)
        if rt_norm and f" {rt_norm} " in query_padded:
            specific_room = rt
            break

    # 2. Distinctive words match (ignoring generic words like 'room', 'rooms', 'type')
    if not specific_room:
        best_matches = 0
        best_rt = None
        for rt in room_types:
            rt_norm = normalize_text(rt.name)
            distinctive_words = [w for w in rt_norm.split() if w not in {'room', 'rooms', 'type', 'types'}]
            matches = 0
            for w in distinctive_words:
                if f" {w} " in query_padded:
                    matches += 1
                elif len(w) >= 5:
                    close = difflib.get_close_matches(w, query_tokens, n=1, cutoff=0.8)
                    if close:
                        matches += 1
            if matches > best_matches:
                best_matches = matches
                best_rt = rt

        if best_matches > 0:
            specific_room = best_rt

    if specific_room:
        desc = specific_room.short_description or specific_room.long_description or ""
        answer = (
            f"{specific_room.name}:\n"
            f"• Tariff: from ₹{specific_room.base_price_per_night:.2f} per night\n"
            f"• Max Occupancy: {specific_room.max_occupancy} guests\n"
            f"• Bedding: {specific_room.bed_type}\n"
        )
        if desc:
            answer += f"• Overview: {desc}\n"
        if hotel_info.rate_note:
            answer += f"\n{hotel_info.rate_note}"

        return {
            "answer": answer.strip(),
            "actions": [
                {"label": "Check Availability", "type": "scroll", "value": "#availability"},
                {"label": "View All Rooms", "type": "scroll", "value": "#rooms"},
            ],
            "matched": True
        }

    # General all rooms list
    lines = ["Here are our available room categories and rates:\n"]
    for rt in room_types:
        lines.append(
            f"• {rt.name}: from ₹{rt.base_price_per_night:.2f} per night "
            f"({rt.bed_type}, up to {rt.max_occupancy} guests)"
        )
    if hotel_info.rate_note:
        lines.append(f"\n{hotel_info.rate_note}")

    return {
        "answer": "\n".join(lines).strip(),
        "actions": [
            {"label": "Check Availability", "type": "scroll", "value": "#availability"},
            {"label": "View Room Details", "type": "scroll", "value": "#rooms"},
        ],
        "matched": True
    }


def _format_facilities_answer() -> Dict[str, Any]:
    """Answers hotel facilities and amenities queries."""
    facilities = list(Facility.objects.all())
    hotel_info = HotelInfo.load()
    contact = _get_contact_info()

    if not facilities and not hotel_info.wifi_info and not hotel_info.parking_info:
        return {
            "answer": (
                f"Facility details have not been entered into our system yet. "
                f"Please call our front desk at {contact.primary_phone} or message us on WhatsApp."
            ),
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    lines = ["Hotel Coral Heights offers the following facilities and guest amenities:\n"]
    for f in facilities:
        lines.append(f"• {f.name}")

    if hotel_info.wifi_info:
        lines.append(f"\nWi-Fi: {hotel_info.wifi_info}")
    if hotel_info.parking_info:
        lines.append(f"Parking: {hotel_info.parking_info}")

    return {
        "answer": "\n".join(lines).strip(),
        "actions": [
            {"label": "View Facilities", "type": "scroll", "value": "#facilities"},
            {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
        ],
        "matched": True
    }


def _format_restaurant_answer(normalized_query: str) -> Dict[str, Any]:
    """Answers restaurant timings, dishes, vegetarian items, and menu queries."""
    restaurant_info = RestaurantInfo.load()
    categories = list(MenuCategory.objects.prefetch_related('items').all())
    all_items = list(MenuItem.objects.select_related('category').all())
    contact = _get_contact_info()

    # Check 1: Specific dish search in MenuItem
    matched_item = None
    for item in all_items:
        it_norm = normalize_text(item.name)
        if it_norm and (it_norm in normalized_query or f" {it_norm} " in f" {normalized_query} "):
            matched_item = item
            break
        # Also check significant word match for dishes like "biryani", "karimeen"
        for word in it_norm.split():
            if len(word) > 4 and f" {word} " in f" {normalized_query} ":
                matched_item = item
                break
        if matched_item:
            break

    if matched_item:
        price_str = f" priced at ₹{matched_item.price:.2f}" if matched_item.price else ""
        veg_str = " (Vegetarian)" if matched_item.is_veg else " (Non-Vegetarian)"
        if matched_item.is_available:
            status_str = f"Yes, '{matched_item.name}'{veg_str} is on our menu under {matched_item.category.name}{price_str}."
        else:
            status_str = f"'{matched_item.name}'{veg_str} is on our menu under {matched_item.category.name}{price_str}, but is currently listed as unavailable today."

        if matched_item.description:
            status_str += f"\nDescription: {matched_item.description}"

        return {
            "answer": status_str,
            "actions": [
                {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # Check 2: Vegetarian enquiry
    is_veg_query = any(w in normalized_query for w in ['veg', 'vegetarian', 'pure veg', 'shakahari'])
    if is_veg_query:
        veg_items = [it for it in all_items if it.is_veg and it.is_available]
        if veg_items:
            lines = ["Yes, we serve delicious vegetarian dishes! Here are some of our vegetarian specialties:\n"]
            for vit in veg_items[:6]:
                p_str = f" — ₹{vit.price:.2f}" if vit.price else ""
                lines.append(f"• {vit.name}{p_str} ({vit.category.name})")
            lines.append("\nPure vegetarian and Jain meals can also be prepared on prior request.")
            return {
                "answer": "\n".join(lines).strip(),
                "actions": [
                    {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                    {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }
        else:
            return {
                "answer": (
                    "Yes, vegetarian dining options are available at our restaurant. "
                    f"Please contact us at {contact.primary_phone} or visit our dining hall for today's vegetarian specialties."
                ),
                "actions": [
                    {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }

    # Check 3: Specific category enquiry
    for cat in categories:
        cat_norm = normalize_text(cat.name)
        if cat_norm and cat_norm in normalized_query:
            available_items = [it for it in cat.items.all() if it.is_available]
            if available_items:
                lines = [f"Here are the items on our {cat.name} menu:\n"]
                for it in available_items:
                    p_str = f" — ₹{it.price:.2f}" if it.price else ""
                    lines.append(f"• {it.name}{p_str}")
                return {
                    "answer": "\n".join(lines).strip(),
                    "actions": [
                        {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                    ],
                    "matched": True
                }

    # Check 4: General Restaurant timings & description
    has_timing = bool(
        restaurant_info.breakfast_hours or restaurant_info.lunch_hours or
        restaurant_info.dinner_hours or restaurant_info.thattukada_hours
    )
    if not has_timing and not restaurant_info.cuisine_description and not categories:
        return {
            "answer": (
                f"Restaurant and menu details have not been entered into our system yet. "
                f"Please contact our front desk at {contact.primary_phone} or WhatsApp for dining timings."
            ),
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    lines = [f"{restaurant_info.name or 'Coral Restaurant'}:\n"]
    if restaurant_info.cuisine_description:
        lines.append(f"{restaurant_info.cuisine_description}\n")

    timing_lines = []
    if restaurant_info.breakfast_hours:
        timing_lines.append(f"• Breakfast: {restaurant_info.breakfast_hours}")
    if restaurant_info.lunch_hours:
        timing_lines.append(f"• Lunch: {restaurant_info.lunch_hours}")
    if restaurant_info.dinner_hours:
        timing_lines.append(f"• Dinner: {restaurant_info.dinner_hours}")
    if restaurant_info.thattukada_hours:
        timing_lines.append(f"• Evening Thattukada: {restaurant_info.thattukada_hours}")
    if restaurant_info.room_service_info:
        timing_lines.append(f"• Room Service: {restaurant_info.room_service_info}")

    if timing_lines:
        lines.append("Timings:\n" + "\n".join(timing_lines))

    if categories:
        cat_names = ", ".join([c.name for c in categories])
        lines.append(f"\nMenu Categories: {cat_names}. Ask about any dish to check prices!")

    if restaurant_info.extra_notes:
        lines.append(f"\nNote: {restaurant_info.extra_notes}")

    return {
        "answer": "\n".join(lines).strip(),
        "actions": [
            {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
            {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
        ],
        "matched": True
    }


def _format_how_to_reach_answer(normalized_query: str) -> Dict[str, Any]:
    """Answers how to reach and transport distance queries."""
    places = list(NearbyPlace.objects.all())
    hotel_info = HotelInfo.load()
    contact = _get_contact_info()

    if not places:
        addr = f"{contact.address_line_1}, {contact.address_line_2}, {contact.address_line_3}"
        return {
            "answer": (
                f"Distance and transport details have not been entered into our system yet. "
                f"Our address is {addr}. Please contact our front desk at {contact.primary_phone} for travel guidance."
            ),
            "actions": [
                {"label": "Call for Directions", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    # Check for specific transport or essential service inquiry
    specific_type = None
    if any(w in normalized_query for w in ['railway', 'station', 'train']):
        specific_type = NearbyPlace.PLACE_TYPE_RAILWAY
    elif any(w in normalized_query for w in ['bus', 'bus stand', 'bus stop', 'ksrtc']):
        specific_type = NearbyPlace.PLACE_TYPE_BUS
    elif any(w in normalized_query for w in ['airport', 'flight', 'aerodrome']):
        specific_type = NearbyPlace.PLACE_TYPE_AIRPORT
    elif any(w in normalized_query for w in ['hospital', 'medical', 'clinic', 'doctor']):
        specific_type = NearbyPlace.PLACE_TYPE_HOSPITAL
    elif any(w in normalized_query for w in ['atm', 'bank']):
        specific_type = NearbyPlace.PLACE_TYPE_ATM_BANK
    elif any(w in normalized_query for w in ['pharmacy', 'medical store', 'chemist']):
        specific_type = NearbyPlace.PLACE_TYPE_PHARMACY

    if specific_type:
        filtered = [p for p in places if p.place_type == specific_type]
        if filtered:
            lines = []
            for p in filtered:
                t_str = f" ({p.travel_time})" if p.travel_time else ""
                lines.append(f"• {p.name}: {p.distance_km} km away{t_str}.")
                if p.directions_note:
                    lines.append(f"  Note: {p.directions_note}")
            return {
                "answer": "\n".join(lines).strip(),
                "actions": [
                    {"label": "Location & Contact", "type": "scroll", "value": "#contact"},
                    {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }

    # General How to Reach: only show Railway Station and Bus Stand, along with landmark note
    reach_places = [
        p for p in places
        if p.place_type in (NearbyPlace.PLACE_TYPE_RAILWAY, NearbyPlace.PLACE_TYPE_BUS)
    ]

    if not reach_places:
        addr = f"{contact.address_line_1}, {contact.address_line_2}, {contact.address_line_3}"
        lines = [
            "Transport details for nearby railway station and bus stand have not been entered into our system yet.",
            f"Our address is: {addr}."
        ]
        if hotel_info.address_note:
            lines.append(f"\nLandmark: {hotel_info.address_note}")
        lines.append(f"\nPlease contact our front desk at {contact.primary_phone} for travel guidance.")
        return {
            "answer": "\n".join(lines).strip(),
            "actions": [
                {"label": "Call for Directions", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    lines = [
        "Hotel Coral Heights is located in Ambalapuzha, Alappuzha. Here are nearby transport hubs:\n"
    ]
    for p in reach_places:
        t_str = f" ({p.travel_time})" if p.travel_time else ""
        lines.append(f"• {p.name}: {p.distance_km} km{t_str}")
        if p.directions_note:
            lines.append(f"  Note: {p.directions_note}")

    if hotel_info.address_note:
        lines.append(f"\nLandmark: {hotel_info.address_note}")

    return {
        "answer": "\n".join(lines).strip(),
        "actions": [
            {"label": "View Contact & Map", "type": "scroll", "value": "#contact"},
            {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
        ],
        "matched": True
    }


def _format_attractions_answer() -> Dict[str, Any]:
    """Answers nearby tourist attractions."""
    attractions = list(Attraction.objects.all())
    contact = _get_contact_info()

    if not attractions:
        return {
            "answer": (
                f"Nearby attractions have not been entered into our system yet. "
                f"Please ask our front desk at {contact.primary_phone} for local sightseeing recommendations."
            ),
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    lines = ["Here are popular tourist spots and attractions near Hotel Coral Heights:\n"]
    for a in attractions:
        desc = f" — {a.description}" if a.description else ""
        lines.append(f"• {a.name} ({a.distance_label}){desc}")

    return {
        "answer": "\n".join(lines).strip(),
        "actions": [
            {"label": "View Attractions", "type": "scroll", "value": "#attractions"},
        ],
        "matched": True
    }


def _format_hotel_info_answer(normalized_query: str) -> Dict[str, Any]:
    """Answers check-in/out times, parking, wifi, payment, languages, pet policy."""
    hotel_info = HotelInfo.load()
    contact = _get_contact_info()

    query_tokens = set(normalized_query.split())
    query_padded = f" {normalized_query} "

    # 1. Payment enquiry
    payment_words = {'payment', 'payments', 'pay', 'card', 'cards', 'credit', 'debit', 'upi', 'gpay', 'cash'}
    if any(w in query_tokens for w in payment_words) or 'google pay' in query_padded or 'phonepe' in query_padded or 'phone pe' in query_padded:
        return {
            "answer": f"Accepted Payment Methods:\n{hotel_info.payment_methods or 'We accept Cash, UPI (Google Pay, PhonePe), and major Credit/Debit Cards.'}",
            "actions": [
                {"label": "Book Online", "type": "scroll", "value": "#availability"},
            ],
            "matched": True
        }

    # 2. Check-in / Check-out timings
    checkin_words = {'checkin', 'checkout', 'samayam'}
    if any(w in query_tokens for w in checkin_words) or 'check in' in query_padded or 'check out' in query_padded:
        return {
            "answer": (
                f"Standard Timings:\n"
                f"• Check-in: {hotel_info.check_in_time}\n"
                f"• Check-out: {hotel_info.check_out_time}\n"
                "Early check-in and late check-out are subject to room availability."
            ),
            "actions": [
                {"label": "Check Availability", "type": "scroll", "value": "#availability"},
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 3. Parking
    parking_words = {'parking', 'car', 'cars', 'vehicle', 'vehicles', 'valet'}
    if any(w in query_tokens for w in parking_words):
        return {
            "answer": f"Parking Information:\n{hotel_info.parking_info or 'Parking is available on-site for staying guests.'}",
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 4. Wi-Fi
    wifi_words = {'wifi', 'wi-fi', 'internet'}
    if any(w in query_tokens for w in wifi_words):
        return {
            "answer": f"Wi-Fi Information:\n{hotel_info.wifi_info or 'High-speed Wi-Fi is available for our guests.'}",
            "actions": [
                {"label": "View Facilities", "type": "scroll", "value": "#facilities"},
            ],
            "matched": True
        }

    # 5. Pet policy
    pet_words = {'pet', 'pets', 'dog', 'dogs', 'cat', 'cats'}
    if any(w in query_tokens for w in pet_words):
        return {
            "answer": f"Pet Policy:\n{hotel_info.pet_policy or 'Pets are not permitted on the hotel premises.'}",
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 6. Languages
    lang_words = {'language', 'languages'}
    if any(w in query_tokens for w in lang_words) or 'speak' in query_tokens:
        return {
            "answer": f"Languages Spoken by Staff:\n{hotel_info.languages_spoken or 'Our staff speak Malayalam and English.'}",
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # General overview
    lines = [
        "Hotel Coral Heights Information & Policies:\n",
        f"• Check-in: {hotel_info.check_in_time} | Check-out: {hotel_info.check_out_time}",
    ]
    if hotel_info.parking_info:
        lines.append(f"• Parking: {hotel_info.parking_info}")
    if hotel_info.wifi_info:
        lines.append(f"• Wi-Fi: {hotel_info.wifi_info}")
    if hotel_info.payment_methods:
        lines.append(f"• Payment: {hotel_info.payment_methods}")
    if hotel_info.pet_policy:
        lines.append(f"• Pets: {hotel_info.pet_policy}")
    if hotel_info.languages_spoken:
        lines.append(f"• Languages: {hotel_info.languages_spoken}")

    return {
        "answer": "\n".join(lines).strip(),
        "actions": [
            {"label": "Check Availability", "type": "scroll", "value": "#availability"},
            {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
        ],
        "matched": True
    }


def _format_contact_answer() -> Dict[str, Any]:
    """Answers phone, WhatsApp, email, and address queries."""
    contact = _get_contact_info()
    hotel_info = HotelInfo.load()

    lines = [
        "Hotel Coral Heights Contact Details:\n",
        f"• Phone: {contact.primary_phone}",
    ]
    if contact.landline_1 or contact.landline_2:
        lines.append(f"• Landline: {contact.landline_1 or ''} {contact.landline_2 or ''}".strip())
    if contact.whatsapp_number:
        lines.append(f"• WhatsApp: {contact.whatsapp_number}")
    if contact.email:
        lines.append(f"• Email: {contact.email}")

    addr = f"{contact.address_line_1}, {contact.address_line_2}, {contact.address_line_3}"
    lines.append(f"• Address: {addr}")
    if hotel_info.address_note:
        lines.append(f"• Landmark: {hotel_info.address_note}")

    return {
        "answer": "\n".join(lines).strip(),
        "actions": [
            {"label": "Call Now", "type": "tel", "value": contact.primary_phone_clean},
            {"label": "Chat on WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            {"label": "View Map", "type": "scroll", "value": "#contact"},
        ],
        "matched": True
    }


def _format_cancellation_answer() -> Dict[str, Any]:
    """Answers cancellation and refund policy."""
    contact = _get_contact_info()
    return {
        "answer": (
            f"Cancellation & Refund Policy:\n\n{CANCELLATION_POLICY}\n\n"
            f"To request a cancellation, please call our front desk directly at {contact.primary_phone} or message us on WhatsApp."
        ),
        "actions": [
            {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
        ],
        "matched": True
    }


def _format_booking_availability_answer() -> Dict[str, Any]:
    """
    Honest response: NEVER states availability or promises anything.
    Directs user to the live Check Availability widget.
    """
    return {
        "answer": (
            "Exact availability and live prices are shown directly in our Check Availability box. "
            "Please select your dates and room type to check vacancies and reserve instantly."
        ),
        "actions": [
            {"label": "Check Availability", "type": "scroll", "value": "#availability"},
        ],
        "matched": True
    }


def _format_events_answer() -> Dict[str, Any]:
    """Answers banquet, catering, and event inquiries."""
    contact = _get_contact_info()
    return {
        "answer": (
            "Hotel Coral Heights hosts banquets, weddings, birthday parties, corporate conferences, "
            "and family gatherings. We offer full catering and event management services.\n\n"
            "Please submit your event details through our enquiry form, and our manager will contact you promptly."
        ),
        "actions": [
            {"label": "Event Enquiry Form", "type": "scroll", "value": "#enquiry"},
            {"label": "Call Us", "type": "tel", "value": contact.primary_phone_clean},
            {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
        ],
        "matched": True
    }


def _record_unanswered_question(text: str) -> None:
    """
    Records an unhandled inquiry into UnansweredQuestion without any personal data.
    Increments count if exact text already exists.
    """
    clean = text.strip()[:300]
    if not clean:
        return
    existing = UnansweredQuestion.objects.filter(text__iexact=clean).first()
    if existing:
        existing.count += 1
        existing.save(update_fields=['count', 'last_asked'])
    else:
        UnansweredQuestion.objects.create(text=clean, count=1)


# ─── Main Public Answering Function ─────────────────────────────────────────

def answer(question: str) -> Dict[str, Any]:
    """
    Rule-based and retrieval answering engine:
    1. Normalize text
    2. Greetings / thanks / farewell
    3. Active ChatFAQ entries (staff entries override defaults)
    4. Built-in topics with live database retrieval
    5. Fallback with quick replies and recording into UnansweredQuestion

    Returns:
        {
            "answer": str,
            "actions": List[Dict[str, str]], # each has 'label', 'type', 'value'
            "matched": bool
        }
    """
    if not question or not question.strip():
        return {
            "answer": "Hello! I am Hotel Coral Heights' assistant. How can I help you today?",
            "actions": _get_default_quick_replies(),
            "matched": True
        }

    normalized = normalize_text(question)
    if not normalized:
        return {
            "answer": "Hello! How can I assist you with your stay at Hotel Coral Heights?",
            "actions": _get_default_quick_replies(),
            "matched": True
        }

    contact = _get_contact_info()

    # 1. Greetings
    if any(f" {w} " in f" {normalized} " for w in GREETING_WORDS) or normalized in GREETING_WORDS:
        # Check if greeting is combined with a question (e.g. "hi what are room rates")
        # If the input has more than 3 words, proceed to matching after greeting check
        if len(normalized.split()) <= 3:
            return {
                "answer": (
                    "Namaskaram! Welcome to Hotel Coral Heights, Ambalapuzha. "
                    "I am the Hotel Assistant. How may I help you today?"
                ),
                "actions": _get_default_quick_replies(),
                "matched": True
            }

    # 2. Thanks
    if any(f" {w} " in f" {normalized} " for w in THANKS_WORDS) or normalized in THANKS_WORDS:
        if len(normalized.split()) <= 4:
            return {
                "answer": "You're most welcome! Feel free to ask if you have any other questions. Have a wonderful day!",
                "actions": _get_default_quick_replies(),
                "matched": True
            }

    # 3. Goodbye
    if any(f" {w} " in f" {normalized} " for w in GOODBYE_WORDS) or normalized in GOODBYE_WORDS:
        if len(normalized.split()) <= 3:
            return {
                "answer": "Goodbye! We look forward to welcoming you to Hotel Coral Heights. Have a safe journey!",
                "actions": [
                    {"label": "Check Availability", "type": "scroll", "value": "#availability"},
                    {"label": "Contact Us", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }

    # 4. Active ChatFAQ match (Staff FAQs take priority)
    faq_match = _match_chat_faqs(normalized)
    if faq_match:
        score, faq = faq_match
        return {
            "answer": faq.answer,
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    # 5. Score Built-in Topics
    topic_hits = {}
    query_padded = f" {normalized} "
    query_tokens = normalized.split()

    for topic, keywords in TOPIC_KEYWORDS.items():
        hits, _ = _match_keywords(normalized, keywords)
        if hits > 0:
            topic_hits[topic] = hits

    # Check if query names any MenuItem or MenuCategory in the live database
    menu_items = list(MenuItem.objects.all())
    for item in menu_items:
        it_norm = normalize_text(item.name)
        if it_norm and (it_norm in normalized or f" {it_norm} " in query_padded):
            topic_hits[TOPIC_RESTAURANT] = topic_hits.get(TOPIC_RESTAURANT, 0) + 3
            break
        matched_distinctive = False
        for word in it_norm.split():
            if len(word) >= 5 and f" {word} " in query_padded:
                topic_hits[TOPIC_RESTAURANT] = topic_hits.get(TOPIC_RESTAURANT, 0) + 2
                matched_distinctive = True
                break
        if matched_distinctive:
            break

    # Check if query names any Attraction in the live database
    attractions = list(Attraction.objects.all())
    for attr in attractions:
        at_norm = normalize_text(attr.name)
        if at_norm and (at_norm in normalized or f" {at_norm} " in query_padded):
            topic_hits[TOPIC_ATTRACTIONS] = topic_hits.get(TOPIC_ATTRACTIONS, 0) + 3
            break
        for word in at_norm.split():
            if len(word) >= 5 and f" {word} " in query_padded and word not in {'beach', 'temple', 'church'}:
                topic_hits[TOPIC_ATTRACTIONS] = topic_hits.get(TOPIC_ATTRACTIONS, 0) + 2
                break

    # Disambiguation between availability/booking intent and tariff/price intent
    tariff_words = {'rate', 'rates', 'tariff', 'tariffs', 'price', 'prices', 'cost', 'pricing', 'charge', 'charges', 'rent', 'vaadaka'}
    has_tariff_words = any(w in query_tokens for w in tariff_words) or 'per night' in normalized or 'how much' in normalized
    if TOPIC_BOOKING in topic_hits and TOPIC_ROOMS in topic_hits:
        if not has_tariff_words:
            # Query is asking about availability / booking rooms -> route to booking
            del topic_hits[TOPIC_ROOMS]
        else:
            # Query is specifically asking about tariffs / prices -> route to rooms_rates
            del topic_hits[TOPIC_BOOKING]

    if topic_hits:
        sorted_topics = sorted(topic_hits.items(), key=lambda x: x[1], reverse=True)
        top_topic, top_score = sorted_topics[0]

        # Check for tie between top two topics
        if len(sorted_topics) > 1:
            second_topic, second_score = sorted_topics[1]
            if top_score == second_score and top_score > 0:
                # Disambiguation question
                t1_label = TOPIC_DISPLAY_NAMES.get(top_topic, top_topic)
                t2_label = TOPIC_DISPLAY_NAMES.get(second_topic, second_topic)
                return {
                    "answer": f"Would you like information about {t1_label} or {t2_label}?",
                    "actions": [
                        {"label": t1_label, "type": "topic", "value": top_topic},
                        {"label": t2_label, "type": "topic", "value": second_topic},
                    ],
                    "matched": True
                }

        # Dispatch matched topic
        if top_topic == TOPIC_BOOKING:
            return _format_booking_availability_answer()
        elif top_topic == TOPIC_ROOMS:
            return _format_rooms_rates_answer(normalized)
        elif top_topic == TOPIC_FACILITIES:
            return _format_facilities_answer()
        elif top_topic == TOPIC_RESTAURANT:
            return _format_restaurant_answer(normalized)
        elif top_topic == TOPIC_HOW_TO_REACH:
            return _format_how_to_reach_answer(normalized)
        elif top_topic == TOPIC_ATTRACTIONS:
            return _format_attractions_answer()
        elif top_topic == TOPIC_HOTEL_INFO:
            return _format_hotel_info_answer(normalized)
        elif top_topic == TOPIC_CONTACT:
            return _format_contact_answer()
        elif top_topic == TOPIC_CANCELLATION:
            return _format_cancellation_answer()
        elif top_topic == TOPIC_EVENTS:
            return _format_events_answer()

    # 6. Fallback / Unanswered
    # Record in UnansweredQuestion
    _record_unanswered_question(question)

    return {
        "answer": (
            "I'm sorry, I don't have information on that yet. "
            f"You can choose one of the topics below or reach our front desk directly at {contact.primary_phone}."
        ),
        "actions": _get_default_quick_replies(),
        "matched": False
    }
