from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    path('', views.home_view, name='home'),
]
