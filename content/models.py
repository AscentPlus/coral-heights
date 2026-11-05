from django.db import models


class RoomType(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    short_description = models.TextField()
    long_description = models.TextField(
        blank=True,
        help_text="Fuller description shown in the room details modal. "
                  "Falls back to short_description if left blank."
    )
    base_price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    max_occupancy = models.IntegerField(default=2)
    bed_type = models.CharField(max_length=50, default='King')
    image_url = models.CharField(max_length=500, blank=True)
    image = models.ImageField(upload_to='room_types/', blank=True, null=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Room Type'
        verbose_name_plural = 'Room Types'

    def __str__(self):
        return self.name

    @property
    def room_count(self):
        return self.rooms.count()

    @property
    def display_image_url(self):
        if self.image:
            try:
                return self.image.url
            except ValueError:
                pass
        return self.image_url


class Room(models.Model):
    room_type = models.ForeignKey(
        RoomType, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ['room_number']
        verbose_name = 'Room'
        verbose_name_plural = 'Rooms'

    def __str__(self):
        return f"Room {self.room_number} ({self.room_type.name})"


DEFAULT_FACILITY_ICON = "M5 13l4 4L19 7"

FACILITY_ICON_MAP = {
    # Wi-Fi / Internet
    'wifi': "M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0",
    'internet': "M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0",

    # Reception / Desk / 24-Hour / Check-in
    'reception': "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    'hour': "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    '24': "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    'desk': "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",

    # Parking / Car / Vehicle
    'parking': "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m0 0h4m-4 0V11m0 0h4m-4 0H7",
    'car': "M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0zM13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10",

    # Coffee / Tea / Breakfast / Beverage
    'coffee': "M18 8h1a4 4 0 010 8h-1M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8zM6 1v3M10 1v3M14 1v3",
    'tea': "M18 8h1a4 4 0 010 8h-1M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8zM6 1v3M10 1v3M14 1v3",
    'maker': "M18 8h1a4 4 0 010 8h-1M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8zM6 1v3M10 1v3M14 1v3",

    # Restaurant / Food / Dining / Banquet / Thattukada
    'restaurant': "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
    'food': "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
    'dining': "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
    'banquet': "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m0 0h4m-4 0V11m0 0h4m-4 0H7",
    'thattukada': "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",

    # Security / Lock / Key / Smart
    'lock': "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
    'security': "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
    'smart': "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
    'key': "M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z",

    # Wheelchair / Disability / Accessibility
    'wheelchair': "M18 10a8 8 0 11-16 0 8 8 0 0116 0zM12 14v4m0 0l-2-2m2 2l2-2",
    'accessibility': "M18 10a8 8 0 11-16 0 8 8 0 0116 0zM12 14v4m0 0l-2-2m2 2l2-2",
    'accessible': "M18 10a8 8 0 11-16 0 8 8 0 0116 0zM12 14v4m0 0l-2-2m2 2l2-2",

    # Quiet / Sound / Sleep / Room / Comfort
    'quiet': "M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z",
    'sleep': "M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z",
    'soundproof': "M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z",

    # Pool / Swim
    'pool': "M4 14C4 14 5 12 7.5 12C10 12 11 14 13.5 14C16 14 17 12 19.5 12C22 12 23 14 23 14M4 19C4 19 5 17 7.5 17C10 17 11 19 13.5 19C16 19 17 17 19.5 17C22 17 23 19 23 19",
    'swim': "M4 14C4 14 5 12 7.5 12C10 12 11 14 13.5 14C16 14 17 12 19.5 12C22 12 23 14 23 14M4 19C4 19 5 17 7.5 17C10 17 11 19 13.5 19C16 19 17 17 19.5 17C22 17 23 19 23 19",

    # Gym / Fitness / Spa
    'gym': "M13 10V3L4 14h7v7l9-11h-7z",
    'fitness': "M13 10V3L4 14h7v7l9-11h-7z",
    'spa': "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",

    # AC / Air / Cooling
    'ac': "M12 3v18m9-9H3",
    'air': "M12 3v18m9-9H3",
    'cooling': "M12 3v18m9-9H3",

    # TV / Cable / Entertainment
    'tv': "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    'television': "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",

    # Power / Generator
    'power': "M13 10V3L4 14h7v7l9-11h-7z",
    'generator': "M13 10V3L4 14h7v7l9-11h-7z",
}


class Facility(models.Model):
    name = models.CharField(max_length=100)
    icon_svg_d = models.TextField(
        blank=True,
        help_text="SVG d attribute for icon rendering (auto-assigned if left blank)")
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Facility'
        verbose_name_plural = 'Facilities'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.icon_svg_d or not self.icon_svg_d.strip():
            name_lower = self.name.lower()
            matched = False
            for kw, svg_d in FACILITY_ICON_MAP.items():
                if kw in name_lower:
                    self.icon_svg_d = svg_d
                    matched = True
                    break
            if not matched:
                self.icon_svg_d = DEFAULT_FACILITY_ICON
        super().save(*args, **kwargs)



class Attraction(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    distance_label = models.CharField(max_length=50, help_text="e.g. 1.5 km")
    image_url = models.CharField(max_length=500, blank=True)
    image = models.ImageField(upload_to='attractions/', blank=True, null=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Attraction'
        verbose_name_plural = 'Attractions'

    def __str__(self):
        return self.name

    @property
    def display_image_url(self):
        if self.image:
            try:
                return self.image.url
            except ValueError:
                pass
        return self.image_url



class ContactInformation(models.Model):
    primary_phone = models.CharField(
        max_length=50, default='+91 9496200777', help_text="Main mobile contact number")
    landline_1 = models.CharField(
        max_length=50, default='0477-2278554', blank=True, help_text="Landline phone number 1")
    landline_2 = models.CharField(
        max_length=50, default='0477-2278555', blank=True, help_text="Landline phone number 2")
    whatsapp_number = models.CharField(
        max_length=50, default='+919496200777', help_text="WhatsApp number (e.g. +919496200777)")
    email = models.EmailField(
        default='info@hotelcoralheights.com', help_text="Hotel email address")
    facebook_url = models.URLField(
        default='https://www.facebook.com/CoralHeightsAmbalapuzha', blank=True, help_text="Facebook page URL")
    instagram_url = models.URLField(
        default='https://www.instagram.com/hotel_coralheights/', blank=True, help_text="Instagram page URL")
    address_line_1 = models.CharField(
        max_length=200, default='Hotel Coral Heights')
    address_line_2 = models.CharField(
        max_length=200, default='Ambalapuzha, Alappuzha')
    address_line_3 = models.CharField(
        max_length=200, default='Kerala — 688 561')

    class Meta:
        verbose_name = 'Contact Information'
        verbose_name_plural = 'Contact Information Settings'

    def __str__(self):
        return "Hotel Contact & Social Settings"

    @property
    def primary_phone_clean(self):
        return self.primary_phone.replace(' ', '').replace('-', '')

    @property
    def whatsapp_url(self):
        clean_num = ''.join(filter(str.isdigit, self.whatsapp_number))
        return f"https://wa.me/{clean_num}"
