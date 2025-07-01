from django.urls import path
from .views import DashboardInsightsView,ChartDataView,TopDataProductsAndServicesView

urlpatterns = [
    path('<int:company_id>/dashboard-insights/', DashboardInsightsView.as_view(), name='dashboard-insights'),
    path('<int:company_id>/chart-data/', ChartDataView.as_view(), name='chart-data'),
    path('<int:company_id>/top-data/', TopDataProductsAndServicesView.as_view(), name='top-data'),
]