from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('staff/', include('staff_panel.urls')),
    path('', include('content.urls')),
    path('', include('bookings.urls')),
    path('enquiries/', include('enquiries.urls')),
]

# Local development media serving (Production requires nginx/caddy reverse-proxy for /media/)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom HTTP error handlers for unconfigured URLs, forbidden access, and server errors
handler404 = 'staff_panel.views.custom_404_view'
handler403 = 'staff_panel.views.custom_403_view'
handler500 = 'staff_panel.views.custom_500_view'





