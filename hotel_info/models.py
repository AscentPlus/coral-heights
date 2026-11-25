from django.db import models


class HotelInfo(models.Model):
    """
    Singleton model for hotel general policies, check-in/out timings,
    parking, Wi-Fi, payments, languages, and pet policy.
    """
    check_in_time = models.CharField(
        max_length=50, default="12:00 PM", blank=True,
        help_text='Standard check-in time, e.g. "12:00 PM"'
    )
    check_out_time = models.CharField(
        max_length=50, default="11:00 AM", blank=True,
        help_text='Standard check-out time, e.g. "11:00 AM"'
    )
    address_note = models.TextField(
        blank=True,
        help_text='Location notes, landmarks or navigation hints.'
    )
    parking_info = models.TextField(
        blank=True,
        help_text='Parking availability, valet info, security.'
    )
    wifi_info = models.TextField(
        blank=True,
        help_text='Wi-Fi availability, speeds, and access details.'
    )
    payment_methods = models.TextField(
        blank=True,
        help_text='Accepted payment methods (Cash, UPI, Cards, Net Banking).'
    )
    languages_spoken = models.TextField(
        blank=True,
        help_text='Languages spoken by front desk and hotel staff.'
    )
    pet_policy = models.TextField(
        blank=True,
        help_text='Pet accommodation policy.'
    )
    extra_notes = models.TextField(
        blank=True,
        help_text='Any additional hotel policies or guest information.'
    )
    rate_note = models.TextField(
        default="Rates vary by date and meal plan. Use the Check Availability box for the exact price.",
        help_text='Rate disclaimer appended to chatbot room rate answers.'
    )

    class Meta:
        verbose_name = 'Hotel General Information'
        verbose_name_plural = 'Hotel General Information'

    def __str__(self):
        return "Hotel General Information"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create()
        return obj


class RestaurantInfo(models.Model):
    """
    Singleton model for on-site restaurant details, dining hours,
    thattukada hours, and room service policies.
    """
    name = models.CharField(
        max_length=150, default="Restaurant", blank=True,
        help_text='Restaurant name (e.g. "Coral Heights Restaurant")'
    )
    cuisine_description = models.TextField(
        blank=True,
        help_text='Cuisine summary (e.g. Traditional Kerala, South Indian, Seafood specialties).'
    )
    breakfast_hours = models.CharField(
        max_length=100, blank=True,
        help_text='Breakfast timings, e.g. "7:30 AM – 10:30 AM"'
    )
    lunch_hours = models.CharField(
        max_length=100, blank=True,
        help_text='Lunch timings, e.g. "12:30 PM – 3:30 PM"'
    )
    dinner_hours = models.CharField(
        max_length=100, blank=True,
        help_text='Dinner timings, e.g. "7:30 PM – 10:30 PM"'
    )
    thattukada_hours = models.CharField(
        max_length=100, blank=True,
        help_text='Evening tea / Thattukada timings, e.g. "4:30 PM – 8:30 PM"'
    )
    room_service_info = models.TextField(
        blank=True,
        help_text='Room service hours and availability.'
    )

    class Meta:
        verbose_name = 'Restaurant Information'
        verbose_name_plural = 'Restaurant Information'

    def __str__(self):
        return self.name or "Restaurant Information"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create()
        return obj


class MenuCategory(models.Model):
    """
    Categories for restaurant menu items (e.g. Breakfast, Starters, Kerala Specials, Beverages).
    """
    name = models.CharField(max_length=100, unique=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Menu Category'
        verbose_name_plural = 'Menu Categories'

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    """
    Dishes and drinks offered in the restaurant.
    """
    category = models.ForeignKey(
        MenuCategory, on_delete=models.PROTECT, related_name='items'
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Price in INR. Leave blank if priced per quantity/season."
    )
    is_veg = models.BooleanField(default=False, verbose_name="Vegetarian")
    is_available = models.BooleanField(default=True, verbose_name="Available")
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Menu Item'
        verbose_name_plural = 'Menu Items'

    def __str__(self):
        return self.name


class NearbyPlace(models.Model):
    """
    Essential transport and public services nearby (distinct from tourist attractions).
    """
    PLACE_TYPE_RAILWAY = 'railway_station'
    PLACE_TYPE_BUS = 'bus_stand'
    PLACE_TYPE_AIRPORT = 'airport'
    PLACE_TYPE_HOSPITAL = 'hospital'
    PLACE_TYPE_ATM = 'atm_bank'
    PLACE_TYPE_PHARMACY = 'pharmacy'
    PLACE_TYPE_OTHER = 'other'

    PLACE_TYPE_CHOICES = [
        (PLACE_TYPE_RAILWAY, 'Railway Station'),
        (PLACE_TYPE_BUS, 'Bus Stand'),
        (PLACE_TYPE_AIRPORT, 'Airport'),
        (PLACE_TYPE_HOSPITAL, 'Hospital'),
        (PLACE_TYPE_ATM, 'ATM / Bank'),
        (PLACE_TYPE_PHARMACY, 'Pharmacy'),
        (PLACE_TYPE_OTHER, 'Other'),
    ]

    place_type = models.CharField(
        max_length=30, choices=PLACE_TYPE_CHOICES, default=PLACE_TYPE_OTHER
    )
    name = models.CharField(max_length=150)
    distance_km = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text="Distance in kilometres from the hotel"
    )
    travel_time = models.CharField(
        max_length=100, blank=True,
        help_text='Estimated travel time, e.g. "10 min by auto"'
    )
    directions_note = models.TextField(
        blank=True,
        help_text='Brief driving/travel directions or navigation hints.'
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'distance_km', 'id']
        verbose_name = 'Nearby Place'
        verbose_name_plural = 'Nearby Places'

    def __str__(self):
        return f"{self.name} ({self.get_place_type_display()} — {self.distance_km} km)"


class ChatFAQ(models.Model):
    """
    Custom Q&A knowledge base entries for the hotel chatbot.
    Staff can provide custom answers to specific topics or keywords.
    """
    question = models.CharField(
        max_length=255,
        help_text="What staff would call this question or common guest inquiry"
    )
    keywords = models.TextField(
        blank=True,
        help_text="Comma-separated trigger words/phrases (may include English, Malayalam, Manglish)"
    )
    answer = models.TextField(
        help_text="Plain text answer returned by the chatbot"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this FAQ is actively answered by the chatbot"
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Chatbot FAQ'
        verbose_name_plural = 'Chatbot FAQs'

    def __str__(self):
        return self.question


class UnansweredQuestion(models.Model):
    """
    Logs guest questions that the chatbot was unable to answer with confidence.
    Privacy safe: strictly records question text and timestamp, no IP, name, or phone.
    """
    text = models.CharField(
        max_length=300,
        help_text="Normalized guest inquiry text"
    )
    count = models.PositiveIntegerField(
        default=1,
        help_text="Number of times this question was asked"
    )
    first_asked = models.DateTimeField(auto_now_add=True)
    last_asked = models.DateTimeField(auto_now=True)
    is_handled = models.BooleanField(
        default=False,
        help_text="Flagged when staff creates a FAQ or marks it addressed"
    )

    class Meta:
        ordering = ['-last_asked']
        verbose_name = 'Unanswered Question'
        verbose_name_plural = 'Unanswered Questions'

    def __str__(self):
        return f'"{self.text[:50]}" ({self.count} times)'

