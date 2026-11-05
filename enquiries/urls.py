from django.urls import path
from .views import submit_enquiry

app_name = 'enquiries'

urlpatterns = [
    path('submit/', submit_enquiry, name='submit'),
]
