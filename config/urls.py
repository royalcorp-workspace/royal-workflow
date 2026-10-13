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
from django.contrib.auth.decorators import login_required
import django_forms_workflows.urls as fw_urls

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


def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('/forms/')
    return redirect('/accounts/login/')


def custom_logout(request):
    logout(request)
    return redirect('/accounts/login/')


urlpatterns = [
    path('', root_redirect, name='root-redirect'),
    path('admin/', admin.site.urls),

    # Override logout agar menerima GET tanpa error 405 dan redirect ke login
    path('accounts/logout/', custom_logout, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('api/notifications/toggle/', toggle_notification_preference, name='toggle_notification_preference'),
    path('api/lookup/jde-customer/', jde_customer_lookup, name='jde_customer_lookup'),

    path('forms/', include('django_forms_workflows.urls')),
    path('_nested_admin/', include('nested_admin.urls')),
]
