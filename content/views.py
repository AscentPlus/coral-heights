from django.shortcuts import render
from .models import RoomType, Facility, Attraction


def home_view(request):
    room_types = RoomType.objects.prefetch_related('rooms').all()
    facilities = Facility.objects.all()
    attractions = Attraction.objects.all()

    context = {
        'room_types': room_types,
        'facilities': facilities,
        'attractions': attractions,
    }
    return render(request, 'content/home.html', context)
