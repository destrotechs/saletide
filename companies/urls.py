from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter
from .views import CompanyViewSet, EmployeeViewSet,EmployeeChoicesAPIView,CompanyPayrollAPI,CompanyRegistrationAPIView

# Main router
router = DefaultRouter()
router.register(r'', CompanyViewSet, basename='company')

# Nested router for employees under companies
company_router = NestedDefaultRouter(router, r'', lookup='company')
company_router.register(r'employees', EmployeeViewSet, basename='company-employees')


urlpatterns = [
    path("", include(router.urls)),  # /api/v1/companies/
    path("", include(company_router.urls)),  # /api/v1/companies/<company_id>/employees/
    path("employee/choices", EmployeeChoicesAPIView.as_view(), name='employee-choices'),
    path("payroll/generate", CompanyPayrollAPI.as_view(), name='payroll'),
    path('company/register/', CompanyRegistrationAPIView.as_view(), name='company_registration'),
]
