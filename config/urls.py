"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required
import django_forms_workflows.urls as fw_urls
from django_forms_workflows.reporting_views import analytics_dashboard

from config.views import (
    custom_form_list,
    custom_form_submit,
    custom_my_submissions,
    custom_my_submissions_ajax,
    toggle_notification_preference,
    jde_customer_lookup,
)

# Pasang custom views untuk form_list, form_submit, my_submissions, my_submissions_ajax
for pattern in fw_urls.urlpatterns:
    if getattr(pattern, 'name', None) == 'form_list':
        pattern.callback = custom_form_list
    elif getattr(pattern, 'name', None) == 'form_submit':
        pattern.callback = custom_form_submit
    elif getattr(pattern, 'name', None) == 'my_submissions':
        pattern.callback = custom_my_submissions
    elif getattr(pattern, 'name', None) == 'my_submissions_ajax':
        pattern.callback = custom_my_submissions_ajax


def custom_logout(request):
    logout(request)
    return redirect('/accounts/login/')


urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='root-redirect'),
    path('dashboard/', analytics_dashboard, name='dashboard'),
    path('admin/', admin.site.urls),

    # Override logout agar menerima GET tanpa error 405 dan redirect ke login
    path('accounts/logout/', custom_logout, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('api/notifications/toggle/', toggle_notification_preference, name='toggle_notification_preference'),
    path('api/lookup/jde-customer/', jde_customer_lookup, name='jde_customer_lookup'),

    # Direct root path for external store partner digital signature portal
    path('spk/sign/', include([
        path('<uuid:token>/', fw_urls.signing_views.public_spk_signing_view, name='root_public_spk_signing'),
        path('<uuid:token>/submit/', fw_urls.signing_views.public_spk_submit_signature, name='root_public_spk_submit_signature'),
        path('<uuid:token>/reject/', fw_urls.signing_views.public_spk_reject_view, name='root_public_spk_reject'),
    ])),

    path('forms/', include('django_forms_workflows.urls')),
    path('_nested_admin/', include('nested_admin.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

