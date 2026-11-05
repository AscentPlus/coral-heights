from django.urls import path
from .views import (
    check_availability,
    send_otp,
    verify_and_hold,
    mock_pay,
    view_receipt,
    view_receipt_pdf,
    booking_page,
)

app_name = 'bookings'

urlpatterns = [
    path('booking/', booking_page, name='booking_page'),
    path('availability/check/', check_availability, name='check_availability'),
    path('bookings/otp/send/', send_otp, name='send_otp'),
    path('bookings/otp/verify-and-hold/',
         verify_and_hold, name='verify_and_hold'),
    path('bookings/<int:booking_id>/mock-pay/', mock_pay, name='mock_pay'),
    path('bookings/<int:booking_id>/<str:token>/receipt/',
         view_receipt, name='receipt'),
    path('bookings/<int:booking_id>/<str:token>/receipt.pdf',
         view_receipt_pdf, name='receipt_pdf'),
]
