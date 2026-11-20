import re
import difflib
import unicodedata
from typing import Dict, Any, List, Optional, Tuple

from bookings.constants import CANCELLATION_POLICY
from content.models import RoomType, Facility, Attraction, ContactInformation
from hotel_info.models import (
    HotelInfo, RestaurantInfo, MenuCategory, MenuItem,
    NearbyPlace, ChatFAQ, UnansweredQuestion
)

# ─── Matching Thresholds & Weights ──────────────────────────────────────────
FAQ_SCORE_THRESHOLD = 0.58
FAQ_KEYWORD_MATCH_WEIGHT = 0.60
FAQ_SIMILARITY_WEIGHT = 0.40
TOPIC_TIE_THRESHOLD = 0.05
DIFFLIB_WORD_SIMILARITY_CUTOFF = 0.88

# ─── Greeting / Farewell Lists ──────────────────────────────────────────────
GREETING_WORDS = [
    'hi', 'hello', 'hey', 'greetings', 'good morning', 'good afternoon',
    'good evening', 'namaskaram', 'namaste', 'halo', 'hai', 'helo',
    'morning', 'evening', 'vanakkam', 'നമസ്കാരം', 'ഹലോ'
]

THANKS_WORDS = [
    'thank you', 'thanks', 'thank u', 'thx', 'nanni', 'valare nanni',
    'dhanyavadham', 'much appreciated', 'thanks a lot', 'thankyou', 'നന്ദി'
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
        'book', 'booking', 'reserve', 'reservation',
        'room availability', 'rooms availability', 'check availability',
        'is room available', 'are rooms available', 'room available', 'rooms available',
        'can i book', 'book now', 'need a room', 'want a room', 'get a room', 'can i get a room',
        'book a room', 'book room', 'room booking', 'reserve a room',
        'free room', 'room free', 'is a room free',
        'vacant room', 'vacant rooms', 'room vacancy', 'room vacancies',
        'muri undo', 'room undo', 'muri kittumo', 'room kittumo', 'book cheyyaan',
        'room on', 'free on', 'rooms on', 'free tomorrow', 'free today',
        'room for tomorrow', 'room tomorrow', 'room tonight', 'room today',
        'check room availability', 'മുറി ബുക്കിംഗ്', 'റൂം ബുക്ക്'
    ],
    TOPIC_ROOMS: [
        'room', 'rooms', 'rate', 'rates', 'tariff', 'tariffs', 'price', 'prices',
        'cost', 'pricing', 'charge', 'charges', 'per night', 'suite', 'deluxe',
        'executive', 'standard', 'occupancy', 'bed', 'vaadaka', 'muri', 'rent',
        'room rate', 'room rates', 'room price', 'room prices', 'room tariff', 'room tariffs',
        'room rent', 'muri vaadaka', 'per day', 'day charge', 'room rate ethraya',
        'muri rent ethra', 'muri vaadaka ethra',
        'മുറിയുടെ നിരക്ക്', 'മുറിയുടെ നിരക്ക് എത്രയാണ്', 'റൂം നിരക്ക്', 'മുറി വാടക',
        'റൂം വാടക', 'വാടക എത്രയാണ്', 'വില എത്രയാണ്', 'നിരക്ക് എത്രയാണ്', 'മുറി', 'മുറികൾ',
        'വാടക', 'നിരക്ക്', 'വില'
    ],
    TOPIC_FACILITIES: [
        'facility', 'facilities', 'amenity', 'amenities', 'pool', 'swimming pool',
        'swimming', 'gym', 'fitness', 'spa',
        'wifi', 'wi-fi', 'internet', 'wlan',
        'parking', 'car parking', 'parking space', 'parking lot', 'valet',
        'ac', 'air conditioning', 'lift',
        'elevator', 'power backup', 'generator', 'security', 'saukaaryam', 'saukaaryangal',
        'wheelchair', 'wheelchair accessible', 'accessible', 'accessibility',
        'സൗകര്യങ്ങൾ'
    ],
    TOPIC_RESTAURANT: [
        'restaurant', 'food', 'dining', 'dine', 'breakfast', 'lunch', 'dinner',
        'thattukada', 'tea', 'coffee', 'snacks', 'menu', 'dishes', 'dish',
        'veg', 'vegetarian', 'non-veg', 'non veg', 'nonveg', 'nonvegetarian', 'seafood', 'fish',
        'biryani', 'biriyani', 'briyani', 'chicken', 'mutton', 'beef', 'pork', 'duck', 'egg',
        'parotta', 'porotta', 'appam', 'dosa', 'idli', 'chapati', 'roti', 'naan', 'curry',
        'fry', 'roast', 'noodles', 'fried rice', 'meals', 'sadya', 'room service', 'kitchen', 'eat',
        'bhakshanam', 'oone', 'chaya', 'kaappi', 'mess', 'kazhikkan', 'kallu',
        'dining hours', 'restaurant hours', 'dinner hours', 'breakfast hours',
        'lunch hours', 'thattukada hours', 'room service hours',
        'bhakshanam samayam', 'food samayam', 'oone samayam', 'dessert', 'ice cream', 'juice',
        'breakfast time', 'what time do you serve breakfast', 'when is breakfast',
        'ഭക്ഷണം', 'ഭക്ഷണ സമയം', 'രാവിലെ ഭക്ഷണം', 'ഉച്ചഭക്ഷണം', 'അത്താഴം'
    ],
    TOPIC_HOW_TO_REACH: [
        'how to reach', 'reach', 'direction', 'directions', 'route', 'way to',
        'railway', 'station', 'train', 'bus', 'bus stand', 'bus stop', 'ksrtc',
        'airport', 'flight', 'auto', 'autorickshaw', 'taxi', 'cab', 'drive',
        'hospital', 'hospitals', 'clinic', 'doctor', 'medical', 'pharmacy', 'chemist',
        'medical store', 'atm', 'bank', 'cash machine',
        'station distance', 'airport distance', 'railway distance', 'bus stand distance',
        'how far is station', 'how far is railway', 'how far is airport', 'how far is bus stand',
        'distance to railway', 'distance to station', 'distance to airport', 'distance to bus',
        'nearby station', 'vazhi', 'ethaan', 'ethan', 'engane ethanam', 'sthalom',
        'where is hotel', 'where is the hotel', 'location of hotel',
        'എങ്ങനെ എത്താം', 'വഴി', 'റെയിൽവേ സ്റ്റേഷൻ'
    ],
    TOPIC_ATTRACTIONS: [
        'attraction', 'attractions', 'sightseeing', 'sight seeing', 'places to visit',
        'tourist', 'tourism', 'visit', 'nearby places to visit', 'temple', 'beach',
        'ambalapuzha temple', 'krishna temple', 'alappuzha beach', 'beach distance',
        'backwaters', 'houseboat', 'lake', 'kaanenda sthalangal'
    ],
    TOPIC_HOTEL_INFO: [
        'check in', 'check-in', 'check out', 'check-out', 'checkin', 'checkout',
        'hotel hours', 'reception hours',
        'pet', 'pets', 'dog', 'dogs', 'cat', 'cats', 'animal', 'animals',
        'pet policy', 'pets allowed', 'dog allowed', 'dogs allowed', 'cat allowed', 'cats allowed',
        'bring pet', 'bring dog', 'pet friendly',
        'payment', 'payments', 'payment methods', 'credit card', 'debit card',
        'upi', 'gpay', 'google pay', 'phonepe', 'cash', 'languages', 'language',
        'english', 'malayalam', 'hindi', 'checkin samayam', 'checkout samayam',
        'check in samayam', 'check out samayam', 'check in eppozhanu', 'checkout eppozhanu',
        'എപ്പോഴാണ് ചെക്ക് ഇൻ', 'ചെക്ക് ഇൻ', 'ചെക്കിൻ', 'ചെക്ക് ഔട്ട്', 'ചെക്കൗട്ട്',
        'എപ്പോഴാണ്', 'ചെക്ക് ഇൻ സമയം', 'ചെക്ക് ഔട്ട് സമയം'
    ],
    TOPIC_CONTACT: [
        'contact', 'phone', 'mobile', 'call', 'telephone', 'number', 'whatsapp',
        'email', 'mail', 'address', 'location', 'map', 'google map', 'where are you located',
        'where are you', 'where are', 'located', 'where located', 'front desk',
        'reception', 'reception desk', 'reach you', 'phone number', 'contact number',
        'staff', 'human', 'person', 'manager', 'receptionist', 'talk to', 'speak to',
        'connect me', 'connect', 'helpdesk', 'support', 'direct call',
        'talk to staff', 'speak to staff', 'talk to human',
        'vilikkan', 'vilikkenda', 'nambur', 'phone nambur',
        'evideyaanu', 'evideya', 'evide', 'sthalom', 'sthalamevide', 'landmark',
        'where is hotel coral heights in ambalapuzha', 'where is hotel coral heights',
        'where is coral heights', 'hotel address', 'ambalapuzha',
        'എവിടെയാണ്', 'എവിടെ', 'സ്ഥലം എവിടെ', 'ഫോൺ നമ്പർ', 'വിളിക്കാൻ'
    ],
    TOPIC_CANCELLATION: [
        'cancel', 'cancellation', 'cancelling', 'refund', 'refunds', 'refundable',
        'cancel policy', 'cancellation policy', 'change date', 'money back',
        'cancel booking', 'can i cancel', 'can i cancel my booking', 'how to cancel',
        'റദ്ദാക്കൽ', 'റദ്ദാക്കാൻ'
    ],
    TOPIC_EVENTS: [
        'event', 'events', 'catering', 'cater', 'wedding', 'marriage', 'engagement',
        'birthday', 'party', 'conference', 'meeting', 'hall', 'banquet', 'banquet hall',
        'auditorium', 'function', 'functions', 'kalyanam'
    ]
}


def normalize_text(text: str) -> str:
    """
    Normalizes input text without breaking Malayalam or other non-Latin scripts.
    Preserves Unicode letters (L), numbers (N), and combining marks (M).
    Replaces punctuation (P), symbols (S), and control chars (C) with spaces.
    """
    if not text:
        return ""
    norm = unicodedata.normalize('NFKC', text).lower()
    res = []
    for ch in norm:
        cat = unicodedata.category(ch)
        if cat.startswith(('L', 'N', 'M')):
            res.append(ch)
        else:
            res.append(' ')
    return re.sub(r'\s+', ' ', ''.join(res)).strip()


def redact_pii(text: str) -> str:
    """Masks identifiable personal data (emails, cards, phone numbers) before logging."""
    if not text:
        return ""
    # 1. Emails
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[REDACTED_EMAIL]', text)
    # 2. Credit/Debit Card numbers (13-19 digits, possibly space/dash separated)
    text = re.sub(r'\b(?:\d[ -]*?){13,19}\b', '[REDACTED_CARD]', text)
    # 3. Phone numbers (10-12 digits, optional +91 or + country prefix)
    text = re.sub(r'(?:\+?91[\-\s]?)?[6-9]\d{9}', '[REDACTED_PHONE]', text)
    text = re.sub(r'\b\d{10,12}\b', '[REDACTED_PHONE]', text)
    return text


def _get_contact_info():
    return ContactInformation.objects.first() or ContactInformation.objects.create()


def _get_default_quick_replies() -> List[Dict[str, str]]:
    """Returns the standard quick-reply action chips with stable intent IDs."""
    contact = _get_contact_info()
    return [
        {"label": "Rooms & Rates", "type": "topic", "value": "rooms_rates", "intent_id": "rooms_rates"},
        {"label": "Restaurant & Menu", "type": "topic", "value": "restaurant", "intent_id": "restaurant"},
        {"label": "Facilities", "type": "topic", "value": "facilities", "intent_id": "facilities"},
        {"label": "How to Reach", "type": "topic", "value": "how_to_reach", "intent_id": "how_to_reach"},
        {"label": "Check-in & Policies", "type": "topic", "value": "hotel_info", "intent_id": "hotel_info"},
        {"label": "Check Availability", "type": "scroll", "value": "#availability"},
        {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
    ]


def _match_keywords(normalized_query: str, keyword_list: List[str]) -> Tuple[int, float]:
    """
    Checks for exact and fuzzy keyword hits in the normalized query.
    Fuzzy match requires length >= 6 and cutoff >= 0.88 to prevent false word overlaps.
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
        elif len(kw_norm) >= 6:
            # Stricter fuzzy match: minimum 6 chars and 0.88 cutoff to avoid false matches (e.g. serve vs reserve)
            unmatched = [t for t in query_tokens if t not in matched_query_words and len(t) >= 6]
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
    Requires genuine topic evidence. Disallows weak fuzzy single-word matches.
    """
    active_faqs = ChatFAQ.objects.filter(is_active=True).order_by('display_order', 'id')
    if not active_faqs.exists():
        return None

    best_faq = None
    best_score = 0.0
    query_padded = f" {normalized_query} "
    query_tokens = normalized_query.split()

    FAQ_SYNONYMS = {
        'bar': ['alcohol', 'liquor', 'beer', 'wine', 'whisky', 'drinks', 'madyam', 'kallu', 'bevco'],
        'alcohol': ['bar', 'liquor', 'beer', 'wine', 'whisky', 'drinks', 'madyam', 'kallu'],
        'hot water': ['geyser', 'chooduvellam', 'warm water', 'hot shower'],
        'swimming pool': ['pool', 'swim', 'swimming', 'kulam'],
        'gym': ['fitness', 'workout', 'exercise'],
    }

    FAQ_STOP_WORDS = {
        'hours', 'hour', 'time', 'times', 'available', 'hotel', 'room',
        'rooms', 'service', 'have', 'does', 'with', 'what', 'where', 'when',
        'your', 'about', 'from', 'this', 'that', 'there', 'they', 'you', 'can',
        'the', 'is', 'are', 'for', 'our', 'in', 'at', 'weather', 'tokyo'
    }

    for faq in active_faqs:
        faq_q_norm = normalize_text(faq.question)
        similarity = difflib.SequenceMatcher(None, normalized_query, faq_q_norm).ratio()

        kw_hits = 0
        raw_keywords = set()
        multi_phrases = []

        if faq.keywords:
            for segment in faq.keywords.split(','):
                seg_norm = normalize_text(segment)
                if not seg_norm:
                    continue
                if ' ' in seg_norm:
                    multi_phrases.append(seg_norm)
                for w in seg_norm.split():
                    if len(w) >= 3 and w not in FAQ_STOP_WORDS:
                        raw_keywords.add(w)

        for w in faq_q_norm.split():
            if len(w) >= 4 and w not in FAQ_STOP_WORDS:
                raw_keywords.add(w)

        all_concepts = list(multi_phrases) + list(raw_keywords) + [faq_q_norm]
        for key, syns in FAQ_SYNONYMS.items():
            if any(key in c for c in all_concepts):
                for syn in syns:
                    if ' ' in syn:
                        multi_phrases.append(syn)
                    elif syn not in FAQ_STOP_WORDS:
                        raw_keywords.add(syn)

        for phrase in multi_phrases:
            if f" {phrase} " in query_padded:
                kw_hits += 2

        matched_tokens = set()
        for kw in raw_keywords:
            if f" {kw} " in query_padded:
                kw_hits += 1
                matched_tokens.add(kw)
            elif len(kw) >= 6:
                unmatched = [t for t in query_tokens if t not in matched_tokens and len(t) >= 6]
                close = difflib.get_close_matches(
                    kw, unmatched, n=1, cutoff=DIFFLIB_WORD_SIMILARITY_CUTOFF
                )
                if close:
                    kw_hits += 1
                    matched_tokens.add(close[0])

        kw_score = min(1.0, kw_hits / 2.0) if kw_hits else 0.0

        if kw_hits >= 2:
            score = (FAQ_KEYWORD_MATCH_WEIGHT * kw_score) + (FAQ_SIMILARITY_WEIGHT * similarity)
            score = max(score, 0.70)
        elif kw_hits == 1:
            # Require question similarity >= 0.38 to prevent false single-word matches in unrelated queries
            if similarity >= 0.38:
                score = (FAQ_KEYWORD_MATCH_WEIGHT * kw_score) + (FAQ_SIMILARITY_WEIGHT * similarity)
            else:
                score = 0.0
        else:
            # No keyword hits: require very strong question text similarity
            score = similarity if similarity >= 0.85 else 0.0

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

    specific_room = None
    query_padded = f" {normalized_query} "
    query_tokens = normalized_query.split()

    for rt in room_types:
        rt_norm = normalize_text(rt.name)
        if rt_norm and f" {rt_norm} " in query_padded:
            specific_room = rt
            break

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
                    close = difflib.get_close_matches(w, query_tokens, n=1, cutoff=0.88)
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


def _format_facilities_answer(normalized_query: str = "") -> Dict[str, Any]:
    """Answers hotel facilities and guest amenities queries, with specific accessibility/elevator support."""
    facilities = list(Facility.objects.all())
    hotel_info = HotelInfo.load()
    contact = _get_contact_info()
    query_padded = f" {normalized_query} " if normalized_query else ""

    # 1. Wheelchair / Accessibility inquiry
    if any(w in query_padded for w in [' wheelchair ', ' accessible ', ' accessibility ', ' disabled ']):
        wheelchair_fac = next((f for f in facilities if 'wheelchair' in f.name.lower() or 'accessib' in f.name.lower()), None)
        if wheelchair_fac:
            ans = f"Yes, Hotel Coral Heights features {wheelchair_fac.name}."
            ans += f"\nFor dedicated wheelchair-accessible room allocation, please contact our front desk at {contact.primary_phone}."
        else:
            ans = f"Wheelchair-accessible rooms and accessibility details are not listed in our standard facility records. Please contact our front desk at {contact.primary_phone} to discuss accessibility requirements and assistance."
        return {
            "answer": ans,
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    # 2. Elevator / Lift inquiry
    if any(w in query_padded for w in [' elevator ', ' lift ', ' elevators ', ' lifts ']):
        elevator_fac = next((f for f in facilities if 'elevator' in f.name.lower() or 'lift' in f.name.lower()), None)
        if elevator_fac:
            ans = f"Yes, Hotel Coral Heights is equipped with an {elevator_fac.name} for guest convenience."
        else:
            ans = f"Elevator and lift facilities are not listed in our standard facility records. Please contact our front desk at {contact.primary_phone} for floor assignment and accessibility assistance."
        return {
            "answer": ans,
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

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
    """Answers dining queries, with strict allergen neutrality, breakfast priority, and dish price quotes."""
    restaurant_info = RestaurantInfo.load()
    categories = list(MenuCategory.objects.prefetch_related('items').all())
    all_items = list(MenuItem.objects.select_related('category').all())
    contact = _get_contact_info()
    query_padded = f" {normalized_query} "
    query_tokens = normalized_query.split()

    # 1. Allergen, allergy, ingredient & cross-contact inquiry (BEFORE ordinary dish matching)
    allergen_terms = [
        'allergy', 'allergic', 'allergens', 'allergen', 'nut', 'nuts', 'peanut', 'peanuts',
        'gluten', 'dairy', 'vegan', 'celiac', 'lactose', 'cross contact', 'cross contamination',
        'cross-contact', 'cross-contamination', 'ingredients', 'ingredient', 'safe for'
    ]
    if any(term in normalized_query for term in allergen_terms):
        return {
            "answer": "Our restaurant team can confirm ingredients and possible cross-contact for this dish. Please contact the restaurant before ordering.",
            "actions": [
                {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

    # 2. Breakfast hours query priority
    if any(w in query_padded for w in [' breakfast ', ' break fast ', ' രാവിലെ ']):
        if restaurant_info.breakfast_hours:
            ans = f"Breakfast: {restaurant_info.breakfast_hours}. Breakfast is served at {restaurant_info.name or 'our restaurant'}."
        else:
            ans = f"Breakfast is served at {restaurant_info.name or 'our restaurant'}. Please contact our front desk at {contact.primary_phone} for current breakfast hours."
        if restaurant_info.cuisine_description:
            ans += f"\nCuisine: {restaurant_info.cuisine_description}"
        return {
            "answer": ans,
            "actions": [
                {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 3. Lunch / Dinner / Thattukada queries
    if any(w in query_padded for w in [' lunch ', ' ഉച്ചഭക്ഷണം ']):
        if restaurant_info.lunch_hours:
            ans = f"Lunch: {restaurant_info.lunch_hours}. Lunch is served at {restaurant_info.name or 'our restaurant'}."
        else:
            ans = f"Lunch is served at {restaurant_info.name or 'our restaurant'}."
        return {
            "answer": ans,
            "actions": [
                {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    if any(w in query_padded for w in [' dinner ', ' അത്താഴം ']):
        if restaurant_info.dinner_hours:
            ans = f"Dinner: {restaurant_info.dinner_hours}. Dinner is served at {restaurant_info.name or 'our restaurant'}."
        else:
            ans = f"Dinner is served at {restaurant_info.name or 'our restaurant'}."
        return {
            "answer": ans,
            "actions": [
                {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 4. Specific dish search in MenuItem (Price quote or availability)
    matched_item = None
    for item in all_items:
        it_norm = normalize_text(item.name)
        if it_norm and (it_norm in normalized_query or f" {it_norm} " in query_padded):
            matched_item = item
            break
        for word in it_norm.split():
            if len(word) >= 5 and f" {word} " in query_padded:
                matched_item = item
                break
        if matched_item:
            break

    if matched_item:
        price_inquiry = any(w in query_tokens for w in ['cost', 'price', 'rate', 'how much', 'ethra', 'charges', 'charge']) or 'how much' in normalized_query
        veg_str = " (Vegetarian)" if matched_item.is_veg else " (Non-Vegetarian)"

        if price_inquiry:
            if matched_item.price is not None:
                ans = f"'{matched_item.name}'{veg_str} is priced at ₹{matched_item.price:.2f}."
            else:
                ans = f"'{matched_item.name}'{veg_str} is on our menu under {matched_item.category.name}. Our restaurant staff can confirm current pricing when you order."
            if matched_item.description:
                ans += f"\nDescription: {matched_item.description}"
            if not matched_item.is_available:
                ans += "\nNote: This item is currently listed as unavailable today."
            return {
                "answer": ans,
                "actions": [
                    {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                    {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }
        else:
            price_str = f" priced at ₹{matched_item.price:.2f}" if matched_item.price is not None else ""
            if matched_item.is_available:
                status_str = f"'{matched_item.name}'{veg_str} is on our menu under {matched_item.category.name}{price_str}."
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

    # 5. Non-Vegetarian enquiry
    nonveg_terms = [
        'non veg', 'nonveg', 'non vegetarian', 'non-veg', 'nonvegetarian',
        'meat', 'chicken', 'mutton', 'beef', 'fish', 'seafood', 'pork', 'duck', 'egg'
    ]
    is_nonveg_query = any(t in normalized_query for t in nonveg_terms)

    # 6. Vegetarian enquiry
    veg_terms = ['vegetarian', 'pure veg', 'shakahari']
    is_veg_query = not is_nonveg_query and (
        any(t in normalized_query for t in veg_terms) or
        'veg' in query_tokens
    )

    if is_nonveg_query:
        dish_inquiry_words = [
            'biryani', 'biriyani', 'briyani', 'chicken fry', 'chicken curry',
            'mutton curry', 'beef roast', 'fish curry', 'fish fry', 'prawns',
            'crab', 'porotta', 'parotta', 'naan', 'roti', 'chapati', 'fried rice',
            'noodles', 'meals', 'sadya', 'chicken', 'mutton', 'beef'
        ]
        specific_dish_asked = None
        for dw in dish_inquiry_words:
            if f" {dw} " in query_padded:
                specific_dish_asked = dw.title()
                break

        if specific_dish_asked:
            lines = [
                f"'{specific_dish_asked}' is not currently listed on our standard dining menu."
            ]
            if restaurant_info.cuisine_description:
                lines.append(f"Our restaurant serves {restaurant_info.cuisine_description}.")
            if restaurant_info.extra_notes:
                lines.append(f"Note: {restaurant_info.extra_notes}")
            else:
                lines.append("Special dishes can often be prepared on prior request.")
            lines.append(f"Please contact our restaurant at {contact.primary_phone} to inquire about today's preparation.")
            return {
                "answer": "\n".join(lines).strip(),
                "actions": [
                    {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                    {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }

        nonveg_items = [it for it in all_items if not it.is_veg and it.is_available]
        if nonveg_items:
            lines = ["Yes, we serve delicious non-vegetarian dishes! Here are some of our non-vegetarian specialties:\n"]
            for nvit in nonveg_items[:6]:
                p_str = f" — ₹{nvit.price:.2f}" if nvit.price else ""
                lines.append(f"• {nvit.name}{p_str} ({nvit.category.name})")
            if restaurant_info.cuisine_description:
                lines.append(f"\nCuisine: {restaurant_info.cuisine_description}")
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
                    f"Yes, non-vegetarian dining options are available. "
                    f"Our restaurant specializes in {restaurant_info.cuisine_description or 'Kerala and Indian cuisine'}. "
                    f"Please contact us at {contact.primary_phone} for today's non-vegetarian menu."
                ),
                "actions": [
                    {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }

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

    # 7. Category enquiry
    for cat in categories:
        cat_norm = normalize_text(cat.name)
        if cat_norm and (cat_norm in normalized_query or f" {cat_norm} " in query_padded):
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

    # 8. General Dish inquiry for other dishes not in MenuItem
    general_dish_words = [
        'biryani', 'biriyani', 'briyani', 'sushi', 'pizza', 'burger', 'sandwich',
        'dosa', 'idli', 'appam', 'puttu', 'porotta', 'parotta', 'chapati', 'roti',
        'naan', 'noodles', 'fried rice', 'soup', 'salad', 'ice cream', 'dessert',
        'juice', 'shake', 'dish', 'item'
    ]
    matched_general_dish = None
    for dw in general_dish_words:
        if f" {dw} " in query_padded:
            matched_general_dish = dw.title()
            break

    if matched_general_dish:
        lines = [
            f"'{matched_general_dish}' is not currently listed on our standard dining menu."
        ]
        if restaurant_info.cuisine_description:
            lines.append(f"Our restaurant serves {restaurant_info.cuisine_description}.")
        if restaurant_info.extra_notes:
            lines.append(f"Note: {restaurant_info.extra_notes}")
        lines.append(f"Please contact our restaurant at {contact.primary_phone} to check if this can be prepared for you.")
        return {
            "answer": "\n".join(lines).strip(),
            "actions": [
                {"label": "Restaurant Details", "type": "scroll", "value": "#restaurant"},
                {"label": "Call Restaurant", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 9. General Restaurant timings & description
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
        addr = f"{contact.address_line_1}, {contact.address_line_2}, {contact.address_line_3}".strip(', ')
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
        specific_type = NearbyPlace.PLACE_TYPE_ATM
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
        else:
            type_names = {
                NearbyPlace.PLACE_TYPE_AIRPORT: "Airport transfer and distance",
                NearbyPlace.PLACE_TYPE_RAILWAY: "Railway station",
                NearbyPlace.PLACE_TYPE_BUS: "Bus stand",
                NearbyPlace.PLACE_TYPE_HOSPITAL: "Nearby hospital and medical facility",
                NearbyPlace.PLACE_TYPE_ATM: "Nearby ATM and banking",
                NearbyPlace.PLACE_TYPE_PHARMACY: "Nearby pharmacy and medical store",
            }
            lbl = type_names.get(specific_type, "Transport")
            return {
                "answer": (
                    f"{lbl} details have not been entered into our transport guide yet. "
                    f"Please contact our front desk at {contact.primary_phone} for travel guidance and assistance."
                ),
                "actions": [
                    {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
                    {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
                ],
                "matched": True
            }

    reach_places = [
        p for p in places
        if p.place_type in (NearbyPlace.PLACE_TYPE_RAILWAY, NearbyPlace.PLACE_TYPE_BUS)
    ]

    if not reach_places:
        addr = f"{contact.address_line_1}, {contact.address_line_2}, {contact.address_line_3}".strip(', ')
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


def _format_attractions_answer(normalized_query: str = "") -> Dict[str, Any]:
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

    if normalized_query:
        query_padded = f" {normalized_query} "
        for a in attractions:
            a_norm = normalize_text(a.name)
            generic_attraction_words = {
                'beach', 'temple', 'park', 'swamy', 'sree', 'visit', 'places',
                'place', 'nearby', 'tourist', 'tourism', 'spots', 'spot', 'sightseeing'
            }
            distinctive_words = [w for w in a_norm.split() if w not in generic_attraction_words]
            if (a_norm and a_norm in normalized_query) or any(len(w) >= 5 and f" {w} " in query_padded for w in distinctive_words):
                desc = f"\nOverview: {a.description}" if a.description else ""
                return {
                    "answer": f"{a.name} is located approximately {a.distance_label} from Hotel Coral Heights.{desc}",
                    "actions": [
                        {"label": "View Attractions", "type": "scroll", "value": "#attractions"},
                        {"label": "Call for Directions", "type": "tel", "value": contact.primary_phone_clean},
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
    checkin_words = {'checkin', 'checkout', 'samayam', 'സമയം', 'എപ്പോഴാണ്'}
    if any(w in query_tokens for w in checkin_words) or 'check in' in query_padded or 'check out' in query_padded or 'ചെക്ക് ഇൻ' in query_padded or 'ചെക്ക് ഔട്ട്' in query_padded:
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
    parking_words = {'parking', 'valet'}
    if any(w in query_tokens for w in parking_words) or 'car parking' in query_padded or 'parking space' in query_padded or 'parking lot' in query_padded:
        ans = f"Parking Information:\n{hotel_info.parking_info}" if hotel_info.parking_info else "Parking is available on-site for staying guests."
        return {
            "answer": ans,
            "actions": [
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 4. Wi-Fi
    wifi_words = {'wifi', 'wi-fi', 'internet', 'wlan', 'hotspot'}
    if any(w in query_tokens for w in wifi_words) or 'wi fi' in query_padded or 'wifi' in query_padded:
        ans = f"Wi-Fi Information:\n{hotel_info.wifi_info}" if hotel_info.wifi_info else "Wi-Fi is not available at our hotel."
        return {
            "answer": ans,
            "actions": [
                {"label": "View Facilities", "type": "scroll", "value": "#facilities"},
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 5. Pet policy
    pet_words = {'pet', 'pets', 'dog', 'dogs', 'cat', 'cats', 'animal', 'animals'}
    if any(w in query_tokens for w in pet_words) or 'pet friendly' in query_padded or 'pets allowed' in query_padded:
        ans = f"Pet Policy:\n{hotel_info.pet_policy or 'Pets are not permitted on the hotel premises.'}"
        return {
            "answer": ans,
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


def _format_contact_answer(normalized_query: str = "") -> Dict[str, Any]:
    """Answers phone, WhatsApp, email, staff, address and location queries."""
    contact = _get_contact_info()
    hotel_info = HotelInfo.load()
    addr = f"{contact.address_line_1}, {contact.address_line_2}, {contact.address_line_3}".strip(', ')

    # Check if specifically asking about address / where located
    addr_words = ['where is', 'address', 'location', 'located', 'where are', 'ambalapuzha', 'sthalom', 'evide', 'evideyaanu']
    if any(w in normalized_query for w in addr_words):
        lines = [
            f"Hotel Coral Heights is located at:\n{addr}"
        ]
        if hotel_info.address_note:
            lines.append(f"\nLandmark: {hotel_info.address_note}")
        lines.append(f"\nFor directions assistance, call us at {contact.primary_phone} or chat on WhatsApp.")
        return {
            "answer": "\n".join(lines).strip(),
            "actions": [
                {"label": "View Location & Map", "type": "scroll", "value": "#contact"},
                {"label": "Call for Directions", "type": "tel", "value": contact.primary_phone_clean},
                {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
            ],
            "matched": True
        }

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

    lines.append(f"• Address: {addr}")
    if hotel_info.address_note:
        lines.append(f"• Landmark: {hotel_info.address_note}")

    if normalized_query and any(w in normalized_query for w in ['staff', 'human', 'person', 'manager', 'receptionist', 'talk', 'speak']):
        lines.append("\nOur front desk staff and management are available 24/7 to assist you directly.")

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
            f"Booking Cancellation & Refund Policy:\n\n{CANCELLATION_POLICY}\n\n"
            f"To cancel a booking or request changes, please call our front desk directly at {contact.primary_phone} or message us on WhatsApp with your booking reference."
        ),
        "actions": [
            {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            {"label": "WhatsApp", "type": "whatsapp", "value": contact.whatsapp_url},
        ],
        "matched": True
    }


def _format_booking_availability_answer() -> Dict[str, Any]:
    """Directs user to the live Check Availability widget."""
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
    Identifiable details (email, card, phone) are redacted before storage.
    """
    clean = redact_pii(text.strip())[:300]
    if not clean:
        return
    existing = UnansweredQuestion.objects.filter(text__iexact=clean).first()
    if existing:
        existing.count += 1
        existing.save(update_fields=['count', 'last_asked'])
    else:
        UnansweredQuestion.objects.create(text=clean, count=1)


def answer_intent(intent_id: str) -> Dict[str, Any]:
    """
    Handles explicit button actions and quick reply chips by stable intent ID.
    Strictly separates button actions from free-text matching.
    """
    intent_norm = normalize_text(intent_id).replace(' ', '_')
    if intent_norm in ('rooms', 'rooms_rates', 'room_categories'):
        return _format_rooms_rates_answer("")
    elif intent_norm in ('restaurant', 'restaurant_menu', 'dining', 'food'):
        return _format_restaurant_answer("")
    elif intent_norm in ('facilities', 'amenities'):
        return _format_facilities_answer("")
    elif intent_norm in ('how_to_reach', 'directions', 'transport'):
        return _format_how_to_reach_answer("")
    elif intent_norm in ('hotel_info', 'checkin_policies', 'checkin', 'policies', 'check_in_policies'):
        return _format_hotel_info_answer("")
    elif intent_norm in ('cancellation', 'refund'):
        return _format_cancellation_answer()
    elif intent_norm in ('events', 'banquet', 'catering'):
        return _format_events_answer()
    elif intent_norm in ('contact', 'phone', 'location'):
        return _format_contact_answer("")
    elif intent_norm in ('booking', 'availability'):
        return _format_booking_availability_answer()
    elif intent_norm in ('attractions', 'sightseeing'):
        return _format_attractions_answer("")
    else:
        return {
            "answer": "Namaskaram! How can I assist you with your stay at Hotel Coral Heights?",
            "actions": _get_default_quick_replies(),
            "matched": True
        }


def answer(question: str, record_unanswered: bool = True) -> Dict[str, Any]:
    """
    Rule-based and retrieval answering engine.
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
        question_words = {'what', 'how', 'when', 'where', 'who', 'is', 'are', 'can', 'do', 'rate', 'room', 'price', 'tariff', 'food', 'menu', 'reach'}
        has_question_word = any(w in normalized.split() for w in question_words)
        if len(normalized.split()) <= 4 and not has_question_word:
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
        question_words = {'what', 'how', 'when', 'where', 'who', 'is', 'are', 'can', 'do', 'rate', 'room', 'price', 'tariff', 'food', 'menu'}
        has_question_word = any(w in normalized.split() for w in question_words)
        if len(normalized.split()) <= 6 or not has_question_word:
            return {
                "answer": "You're most welcome! Feel free to ask if you have any other questions. Have a wonderful day!",
                "actions": _get_default_quick_replies(),
                "matched": True
            }

    # 3. Goodbye
    if any(f" {w} " in f" {normalized} " for w in GOODBYE_WORDS) or normalized in GOODBYE_WORDS:
        question_words = {'what', 'how', 'when', 'where', 'who', 'is', 'are', 'can', 'do', 'rate', 'room', 'price', 'tariff', 'food', 'menu'}
        has_question_word = any(w in normalized.split() for w in question_words)
        if len(normalized.split()) <= 6 or not has_question_word:
            return {
                "answer": "Goodbye! We look forward to welcoming you to Hotel Coral Heights. Have a safe journey!",
                "actions": [
                    {"label": "Check Availability", "type": "scroll", "value": "#availability"},
                    {"label": "Contact Us", "type": "tel", "value": contact.primary_phone_clean},
                ],
                "matched": True
            }

    # 4. Cancellation priority check
    cancellation_signals = ['cancel', 'cancellation', 'cancelling', 'refund', 'refunds', 'റദ്ദാക്കൽ']
    if any(s in normalized.split() for s in cancellation_signals) or 'cancel my booking' in normalized or 'cancel booking' in normalized:
        return _format_cancellation_answer()

    # 5. Dual-intent check: Booking + Check-in
    booking_signals = ['book', 'booking', 'reserve', 'reservation', 'room for tomorrow', 'available tomorrow', 'vacant', 'vacancy']
    checkin_signals = ['check in', 'check-in', 'checkin', 'check out', 'checkout', 'samayam', 'timings', 'timing', 'times', 'time']
    has_booking_intent = any(s in normalized for s in booking_signals)
    has_checkin_intent = any(s in normalized for s in checkin_signals)

    if has_booking_intent and has_checkin_intent:
        hotel_info = HotelInfo.load()
        return {
            "answer": (
                f"• Check-in & Check-out: Standard check-in is at {hotel_info.check_in_time} and check-out is at {hotel_info.check_out_time}.\n"
                f"• Room Availability & Booking: Exact room availability and live prices for tomorrow can be checked directly in our Check Availability box."
            ),
            "actions": [
                {"label": "Check Availability", "type": "scroll", "value": "#availability"},
                {"label": "Call Front Desk", "type": "tel", "value": contact.primary_phone_clean},
            ],
            "matched": True
        }

    # 6. Address / Location specific inquiry check
    if 'where is hotel coral heights' in normalized or ('where is' in normalized and 'hotel' in normalized) or 'where is coral heights' in normalized:
        return _format_contact_answer(normalized)

    # 7. Allergen / Ingredient check (priority before ordinary matching)
    allergen_terms = [
        'allergy', 'allergic', 'allergens', 'allergen', 'nut', 'nuts', 'peanut', 'peanuts',
        'gluten', 'dairy', 'vegan', 'celiac', 'lactose', 'cross contact', 'cross contamination',
        'cross-contact', 'cross-contamination', 'ingredients', 'ingredient', 'safe for'
    ]
    if any(term in normalized for term in allergen_terms):
        return _format_restaurant_answer(normalized)

    # 8. Active ChatFAQ match
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

    # 9. Score Built-in Topics
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

    # Accessibility / Elevator queries route directly to facilities
    if any(w in query_padded for w in [' wheelchair ', ' accessible ', ' accessibility ', ' elevator ', ' lift ']):
        return _format_facilities_answer(normalized)

    # Disambiguation between availability/booking intent and tariff/price intent
    tariff_words = {'rate', 'rates', 'tariff', 'tariffs', 'price', 'prices', 'cost', 'pricing', 'charge', 'charges', 'rent', 'vaadaka', 'നിരക്ക്', 'വാടക', 'വില'}
    has_tariff_words = any(w in query_tokens for w in tariff_words) or 'per night' in normalized or 'how much' in normalized
    if TOPIC_BOOKING in topic_hits and TOPIC_ROOMS in topic_hits:
        if not has_tariff_words:
            del topic_hits[TOPIC_ROOMS]
        else:
            del topic_hits[TOPIC_BOOKING]

    # Disambiguation between Hotel Info (languages) and Contact (staff)
    if TOPIC_HOTEL_INFO in topic_hits and TOPIC_CONTACT in topic_hits:
        if any(w in query_tokens for w in ['language', 'languages', 'english', 'malayalam', 'hindi', 'tamil', 'speak']):
            del topic_hits[TOPIC_CONTACT]

    if topic_hits:
        sorted_topics = sorted(topic_hits.items(), key=lambda x: x[1], reverse=True)
        top_topic, top_score = sorted_topics[0]

        if len(sorted_topics) > 1:
            second_topic, second_score = sorted_topics[1]
            if top_score == second_score and top_score > 0:
                t1_label = TOPIC_DISPLAY_NAMES.get(top_topic, top_topic)
                t2_label = TOPIC_DISPLAY_NAMES.get(second_topic, second_topic)
                return {
                    "answer": f"Would you like information about {t1_label} or {t2_label}?",
                    "actions": [
                        {"label": t1_label, "type": "topic", "value": top_topic, "intent_id": top_topic},
                        {"label": t2_label, "type": "topic", "value": second_topic, "intent_id": second_topic},
                    ],
                    "matched": True
                }

        if top_topic == TOPIC_BOOKING:
            return _format_booking_availability_answer()
        elif top_topic == TOPIC_ROOMS:
            return _format_rooms_rates_answer(normalized)
        elif top_topic == TOPIC_FACILITIES:
            return _format_facilities_answer(normalized)
        elif top_topic == TOPIC_RESTAURANT:
            return _format_restaurant_answer(normalized)
        elif top_topic == TOPIC_HOW_TO_REACH:
            return _format_how_to_reach_answer(normalized)
        elif top_topic == TOPIC_ATTRACTIONS:
            return _format_attractions_answer(normalized)
        elif top_topic == TOPIC_HOTEL_INFO:
            return _format_hotel_info_answer(normalized)
        elif top_topic == TOPIC_CONTACT:
            return _format_contact_answer(normalized)
        elif top_topic == TOPIC_CANCELLATION:
            return _format_cancellation_answer()
        elif top_topic == TOPIC_EVENTS:
            return _format_events_answer()

    # 10. Fallback / Unanswered
    if record_unanswered:
        _record_unanswered_question(question)

    return {
        "answer": (
            "I'm sorry, I don't have information on that yet. "
            f"You can choose one of the topics below or reach our front desk directly at {contact.primary_phone}."
        ),
        "actions": _get_default_quick_replies(),
        "matched": False
    }
