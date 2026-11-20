from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.urls import reverse
from .models import RoomType, Facility, Attraction, ContactInformation
from hotel_info.models import HotelInfo, RestaurantInfo, MenuCategory, NearbyPlace


def home_view(request):
    room_types = RoomType.objects.prefetch_related('rooms').all()
    facilities = Facility.objects.all()
    attractions = Attraction.objects.all()
    hotel_info = HotelInfo.objects.first()
    restaurant_info = RestaurantInfo.objects.first()
    contact_info = ContactInformation.objects.first()

    enquiry_errors = request.session.pop('enquiry_errors', None)
    enquiry_data = request.session.pop('enquiry_data', None)

    context = {
        'room_types': room_types,
        'facilities': facilities,
        'attractions': attractions,
        'hotel_info': hotel_info,
        'restaurant_info': restaurant_info,
        'contact_info': contact_info,
        'enquiry_errors': enquiry_errors,
        'enquiry_data': enquiry_data or {},
    }
    return render(request, 'content/home.html', context)


def room_detail_view(request, slug):
    room_type = get_object_or_404(RoomType, slug=slug)
    facilities = Facility.objects.all()
    hotel_info = HotelInfo.objects.first()
    contact_info = ContactInformation.objects.first()
    other_rooms = RoomType.objects.exclude(id=room_type.id)[:3]

    check_in = request.GET.get('check_in', '').strip()
    check_out = request.GET.get('check_out', '').strip()
    adults = request.GET.get('adults', '2').strip()
    children = request.GET.get('children', '0').strip()

    context = {
        'room_type': room_type,
        'facilities': facilities,
        'hotel_info': hotel_info,
        'contact_info': contact_info,
        'other_rooms': other_rooms,
        'check_in': check_in,
        'check_out': check_out,
        'adults': adults,
        'children': children,
    }
    return render(request, 'content/room_detail.html', context)


def dining_view(request):
    restaurant_info = RestaurantInfo.objects.first()
    categories = MenuCategory.objects.prefetch_related('items').order_by('display_order')
    contact_info = ContactInformation.objects.first()

    context = {
        'restaurant_info': restaurant_info,
        'categories': categories,
        'contact_info': contact_info,
    }
    return render(request, 'content/dining.html', context)


def events_view(request):
    return redirect('/#events')


def location_view(request):
    contact_info = ContactInformation.objects.first()
    hotel_info = HotelInfo.objects.first()
    transit_places = NearbyPlace.objects.filter(
        place_type__in=['railway_station', 'bus_stand', 'airport']
    ).order_by('display_order')
    essential_places = NearbyPlace.objects.exclude(
        place_type__in=['railway_station', 'bus_stand', 'airport']
    ).order_by('display_order')
    attractions = Attraction.objects.all().order_by('display_order')

    context = {
        'contact_info': contact_info,
        'hotel_info': hotel_info,
        'transit_places': transit_places,
        'essential_places': essential_places,
        'attractions': attractions,
    }
    return render(request, 'content/location.html', context)


def sitemap_view(request):
    base_url = request.build_absolute_uri('/')[:-1]
    room_types = RoomType.objects.all()

    urls = [
        f"{base_url}{reverse('content:home')}",
        f"{base_url}{reverse('content:dining')}",
        f"{base_url}{reverse('content:location')}",
        f"{base_url}{reverse('bookings:booking_page')}",
    ]
    for rt in room_types:
        urls.append(f"{base_url}{reverse('content:room_detail', kwargs={'slug': rt.slug})}")

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url in urls:
        xml.append('  <url>')
        xml.append(f'    <loc>{url}</loc>')
        xml.append('    <changefreq>weekly</changefreq>')
        xml.append('  </url>')
    xml.append('</urlset>')

    return HttpResponse('\n'.join(xml), content_type='application/xml')
