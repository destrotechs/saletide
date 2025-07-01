"""
URL configuration for csm project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/v1/companies/", include("companies.urls")),
    path("api/v1/auth/", include("core.urls")),
    path("api/v1/services/", include("services.urls")),
    path("api/v1/inventory/", include("inventory.urls")),
    path("api/v1/customers/", include("customers.urls")),
    path("api/v1/sales/", include("sales_invoices.urls")),
    path("api/v1/payments/", include("mpesapayments.urls")),
    path("api/v1/reports/", include("reports.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)