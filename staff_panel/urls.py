from django.urls import path
from . import views

app_name = 'staff_panel'

urlpatterns = [
    path('login/', views.staff_login, name='login'),
    path('logout/', views.staff_logout, name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('bookings/', views.bookings_list, name='bookings'),
    path('bookings/<int:booking_id>/',
         views.booking_detail, name='booking_detail'),
    path('bookings/<int:booking_id>/quick-action/',
         views.booking_quick_action, name='booking_quick_action'),
    path('enquiries/', views.enquiries_list, name='enquiries'),
    path('enquiries/<int:enquiry_id>/',
         views.enquiry_detail, name='enquiry_detail'),
    path('rooms/', views.rooms_list, name='rooms'),
    path('reports/', views.reports_view, name='reports'),
    path('website/', views.website_dashboard, name='website'),
    path('website/room-types/', views.website_room_types, name='website_room_types'),
    path('website/room-types/<int:pk>/delete/', views.website_room_type_delete, name='website_room_type_delete'),
    path('website/facilities/', views.website_facilities, name='website_facilities'),
    path('website/facilities/<int:pk>/delete/', views.website_facility_delete, name='website_facility_delete'),
    path('website/attractions/', views.website_attractions, name='website_attractions'),
    path('website/attractions/<int:pk>/delete/', views.website_attraction_delete, name='website_attraction_delete'),
    path('website/contact/', views.website_contact, name='website_contact'),
    path('manage-staff/', views.manage_staff, name='manage_staff'),
    path('profile/', views.profile, name='profile'),
]
