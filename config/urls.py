"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from leads import views as lead_views

urlpatterns = [
    path('', RedirectView.as_view(url='/sateiinfo/', permanent=False)),
    path('login/', lead_views.google_login_page, name='login'),
    path('login/google/', lead_views.google_login, name='google_login'),
    path('logout/', lead_views.logout_view, name='logout'),
    path('admin/', admin.site.urls),
    path('sateiinfo/', include('leads.urls')),
]
