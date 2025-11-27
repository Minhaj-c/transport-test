"""
Main URL Configuration for Transport System
"""

from django.contrib import admin
from django.urls import path, include
from users.api_views import signup_view, login_view, logout_view, user_profile_view
from routes.views import api_welcome
from users.web_views import web_login, web_logout

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # API Welcome
    path('api/', api_welcome, name='api-welcome'),
    
    # Authentication APIs
    path('api/signup/', signup_view, name='api-signup'),
    path('api/login/', login_view, name='api-login'),
    path('api/logout/', logout_view, name='api-logout'),
    path('api/profile/', user_profile_view, name='api-profile'),
    
    # Include app URLs
    path('', include('routes.urls')),
    path('', include('schedules.urls')),
    path('', include('preinforms.urls')),
    path('', include('demand.urls')),
    path('', include('operations.urls')),
    path('zonal-admin/', include('zonaladmin.urls')),
    path('login/', web_login, name='web-login'),
    path('logout/', web_logout, name='web-logout'),
]