from django.urls import path
from .views import mpesa_callback
from .views import mpesa_confirmation, mpesa_validation,MpesaPaymentView

urlpatterns = [
    path('confirmation/', mpesa_confirmation, name="mpesa_confirmation"),
    path('validation/', mpesa_validation, name="mpesa_validation"),
    path('callback/', mpesa_callback, name="mpesa_callback"),
    path('initiate-payment/', MpesaPaymentView.as_view(), name="initiate_payment"),
]
