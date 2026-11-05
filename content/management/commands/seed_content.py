from django.core.management.base import BaseCommand
from content.models import RoomType, Room, Facility, Attraction


class Command(BaseCommand):
    help = "Seed initial prototype content (RoomTypes, Rooms, Facilities, Attractions)"

    def handle(self, *args, **options):
        self.stdout.write("Seeding room types...")

        deluxe, _ = RoomType.objects.update_or_create(
            slug='deluxe',
            defaults={
                'name': 'Deluxe Room',
                'short_description': 'The spacious Deluxe Room with a king-size bed has everything you could want, from a superb bed to state-of-the-art facilities.',
                'base_price_per_night': 3200.00,
                'max_occupancy': 3,
                'bed_type': 'King',
                'image_url': 'https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800&q=80&auto=format&fit=crop',
                'display_order': 1,
            }
        )

        standard, _ = RoomType.objects.update_or_create(
            slug='standard',
            defaults={
                'name': 'Standard Room',
                'short_description': 'Elegantly designed to charm the most discerning guest — ideal for both leisure and business travellers.',
                'base_price_per_night': 2200.00,
                'max_occupancy': 2,
                'bed_type': 'Double',
                'image_url': 'https://images.unsplash.com/photo-1566665797739-1674de7a421a?w=800&q=80&auto=format&fit=crop',
                'display_order': 2,
            }
        )

        suite, _ = RoomType.objects.update_or_create(
            slug='suite',
            defaults={
                'name': 'Suite Room',
                'short_description': 'A spacious bedroom with a living area, designed to make you feel at home, with comfortable sofa furnishings.',
                'base_price_per_night': 5500.00,
                'max_occupancy': 4,
                'bed_type': 'King',
                'image_url': 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?w=800&q=80&auto=format&fit=crop',
                'display_order': 3,
            }
        )

        self.stdout.write("Seeding inventory rooms...")
        for num in ['101', '102', '103', '104', '105']:
            Room.objects.get_or_create(
                room_number=num, defaults={'room_type': deluxe})
        for num in ['201', '202', '203', '204', '205']:
            Room.objects.get_or_create(room_number=num, defaults={
                                       'room_type': standard})
        for num in ['301', '302', '303']:
            Room.objects.get_or_create(
                room_number=num, defaults={'room_type': suite})

        self.stdout.write("Seeding facilities...")
        facilities_data = [
            ("Smart Lock & Security", '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/><circle cx="12" cy="16" r="1"/>', 1),
            ("24-Hour Reception",
             '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>', 2),
            ("Wheelchair Accessibility", '<circle cx="12" cy="4" r="2"/><path d="M14 22l-2-6H6l1-4h5"/><path d="M6 10l-1 4"/><circle cx="8" cy="20" r="2"/><circle cx="16" cy="20" r="2"/><path d="M12 16h6l-2 6"/>', 3),
            ("Coffee/Tea Maker", '<path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><path d="M6 1v3"/><path d="M10 1v3"/><path d="M14 1v3"/>', 4),
            ("Banquet Facilities", '<path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 21v-4h6v4"/><path d="M9 10h1"/><path d="M14 10h1"/><path d="M9 14h1"/><path d="M14 14h1"/>', 5),
            ("Quiet Rooms", '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>', 6),
            ("Restaurant & Thattukada", '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 002-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 00-5 5v6c0 1.1.9 2 2 2h3zm0 0v7"/>', 7),
            ("Lobby Seating Area", '<path d="M20 10c0-4.4-3.6-8-8-8s-8 3.6-8 8 3.6 8 8 8h8"/><path d="M4 18v2"/><path d="M20 18v2"/><path d="M12 18v4"/><path d="M2 22h20"/>', 8),
        ]
        for name, svg_d, order in facilities_data:
            Facility.objects.update_or_create(
                name=name,
                defaults={'icon_svg_d': svg_d, 'display_order': order}
            )

        self.stdout.write("Seeding attractions...")
        attractions_data = [
            ("Sree Krishna Temple", "The legendary Ambalapuzha temple, famous for its Palpayasam offering and stunning traditional architecture.",
             "1.5 km", "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=600&q=80&auto=format&fit=crop", 1),
            ("Kuttanad", 'The "Rice Bowl of Kerala" — breathtaking paddy fields farmed below sea level.', "8 km",
             "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?w=600&q=80&auto=format&fit=crop", 2),
            ("Nehru Trophy Boat Race", "The world-famous snake boat race held annually on the Punnamada Lake in Alleppey.",
             "12 km", "https://images.unsplash.com/photo-1544644181-1484b3fdfc62?w=600&q=80&auto=format&fit=crop", 3),
            ("Houseboat Trip", "Drift through tranquil backwaters on a traditional kettuvallam houseboat.", "5 km",
             "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=600&q=80&auto=format&fit=crop", 4),
            ("Toddy Shop Visit", "Experience authentic Kerala cuisine and fresh palm toddy at a traditional toddy shop.",
             "3 km", "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600&q=80&auto=format&fit=crop", 5),
            ("Vembanad Lake", "Kerala's longest lake — a Ramsar-designated wetland of extraordinary natural beauty.",
             "10 km", "https://images.unsplash.com/photo-1506929562872-bb421503ef21?w=600&q=80&auto=format&fit=crop", 6),
        ]
        for name, desc, dist, img, order in attractions_data:
            Attraction.objects.update_or_create(
                name=name,
                defaults={'description': desc, 'distance_label': dist,
                          'image_url': img, 'display_order': order}
            )

        self.stdout.write(self.style.SUCCESS(
            "Database successfully seeded with prototype content!"))
