from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('ask/', views.chat_ask, name='ask'),
    path('topics/', views.chat_topics, name='topics'),
]

