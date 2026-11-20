from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('rooms/<slug:slug>/', views.room_detail_view, name='room_detail'),
    path('dining/', views.dining_view, name='dining'),
    path('events/', views.events_view, name='events'),
    path('location/', views.location_view, name='location'),
    path('sitemap.xml', views.sitemap_view, name='sitemap'),
]
