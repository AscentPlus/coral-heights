from django.urls import path
from . import views
import hotel_info.views as hotel_views

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
    path('enquiries/<int:enquiry_id>/retry-notification/',
         views.retry_enquiry_notification, name='retry_enquiry_notification'),
    path('rooms/', views.rooms_list, name='rooms'),
    path('reports/', views.reports_view, name='reports'),
    path('website/', views.website_dashboard, name='website'),
    path('website/room-types/', views.website_room_types, name='website_room_types'),
    path('website/room-types/<int:pk>/delete/', views.website_room_type_delete, name='website_room_type_delete'),
    path('website/facilities/', views.website_facilities, name='website_facilities'),
    path('website/facilities/<int:pk>/delete/', views.website_facility_delete, name='website_facility_delete'),
    path('website/attractions/', views.website_attractions, name='website_attractions'),
    path('website/attractions/<int:pk>/delete/', views.website_attraction_delete, name='website_attraction_delete'),
    path('website/gallery/', views.website_gallery, name='website_gallery'),
    path('website/gallery/<int:pk>/delete/', views.website_gallery_delete, name='website_gallery_delete'),
    path('website/contact/', views.website_contact, name='website_contact'),
    # Hotel & Restaurant Details / Chatbot Info
    path('website/hotel-info/', hotel_views.website_hotel_details, name='website_hotel_details'),
    path('website/restaurant/', hotel_views.website_restaurant_details, name='website_restaurant_details'),
    path('website/menu/', hotel_views.website_menu, name='website_menu'),
    path('website/menu/category/<int:pk>/delete/', hotel_views.website_menu_category_delete, name='website_menu_category_delete'),
    path('website/menu/item/<int:pk>/delete/', hotel_views.website_menu_item_delete, name='website_menu_item_delete'),
    path('website/nearby-places/', hotel_views.website_nearby_places, name='website_nearby_places'),
    path('website/nearby-places/<int:pk>/delete/', hotel_views.website_nearby_place_delete, name='website_nearby_place_delete'),
    path('website/faqs/', hotel_views.website_faqs, name='website_faqs'),
    path('website/faqs/<int:pk>/toggle/', hotel_views.website_faq_toggle, name='website_faq_toggle'),
    path('website/faqs/<int:pk>/delete/', hotel_views.website_faq_delete, name='website_faq_delete'),
    path('website/unanswered-questions/', hotel_views.website_unanswered_questions, name='website_unanswered_questions'),
    path('website/unanswered-questions/<int:pk>/handle/', hotel_views.website_unanswered_handle, name='website_unanswered_handle'),
    path('website/unanswered-questions/<int:pk>/delete/', hotel_views.website_unanswered_delete, name='website_unanswered_delete'),
    path('manage-staff/', views.manage_staff, name='manage_staff'),
    path('profile/', views.profile, name='profile'),
]
