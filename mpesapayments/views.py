from time import timezone

import requests
from django.conf import settings
import json
import base64
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework.views import APIView
from sales_invoices.models import Payment
def get_mpesa_token():
    """Fetches M-Pesa OAuth access token"""
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url, auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET))

    if response.status_code == 200:
        print("Token Response ",json.dumps(response.json(), indent=4))

        return response.json().get('access_token')
    return None
def format_phone_number(number):
    print("Number ",number)
    if number.startswith("0"):
        return "254" + number[1:]
    return number
def lipa_na_mpesa(phone_number, amount,invoice=None,sale=None):
    token = get_mpesa_token()
    if not token:
        return {"error": "Failed to authenticate"}

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()).decode()

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": 1,
        "PartyA": format_phone_number(phone_number),
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": format_phone_number(phone_number),
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": "CSM Test Payment",
        "TransactionDesc": "Payment"
    }

    response = requests.post(url, json=payload, headers=headers)
    print("Lipa Na Mpesa response ",response.json())
    response_dict = json.loads(json.dumps(response.json(), indent=4))
    payment = Payment.objects.create(
        checkoutrequest_id=response_dict.get('CheckoutRequestID'),
        amount_paid=amount,
        payment_method='MPesa'
    )

    return json.loads(json.dumps(response.json(), indent=4))
def generate_password():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password_str = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode()
    return password, timestamp

def query_stk_push_status(checkoutrequest_id):
    password, timestamp = generate_password()
    token = get_mpesa_token()

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkoutrequest_id
    }

    response = requests.post(url, json=payload, headers=headers)
    print("Query STK Push Status response ",json.dumps(response.json(), indent=4))
    return json.loads(json.dumps(response.json(), indent=4))

@csrf_exempt
def mpesa_callback(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            print("Mpesa callback ",data)
            # Extract callback details
            callback = data.get("Body", {}).get("stkCallback", {})
            result_code = callback.get("ResultCode", None)
            checkoutrequestid = callback.get("CheckoutRequestID",None)

            print("Processing payment with checkoutrequestid ", checkoutrequestid)
            # Process only successful transactions
            if result_code == 0:
                metadata = callback.get("CallbackMetadata", {}).get("Item", [])

                # Extract key values from the metadata
                amount = None
                mpesa_receipt_number = None
                transaction_date = None
                phone_number = None
                for item in metadata:
                    if item["Name"] == "Amount":
                        amount = item["Value"]
                    elif item["Name"] == "MpesaReceiptNumber":
                        mpesa_receipt_number = item["Value"]
                    elif item["Name"] == "TransactionDate":
                        transaction_date = item["Value"]
                    elif item["Name"] == "PhoneNumber":
                        phone_number = item["Value"]

                # Convert timestamp to Django DateTime format
                from datetime import datetime
                if transaction_date:
                    transaction_date = datetime.strptime(str(transaction_date), "%Y%m%d%H%M%S")

                # Save to Payment model
                print("Saving transaction")
                payment = Payment.objects.filter(checkoutrequest_id=checkoutrequestid).first()

                payment.amount_paid = amount
                payment.date_paid = transaction_date
                payment.payment_method ='mpesa'
                payment.transaction_id = mpesa_receipt_number
                payment.remarks = f"Payment from {phone_number}"

                payment.save()
                print("Saved transaction")

                # if payment:
                #     PaymentInvoice.objects.create(
                #         payment = payment,
                #         invoice=payment.invoice
                #     )

                return JsonResponse({"ResultCode": 0, "ResultDesc": "Success", "PaymentID": payment.id})

            else:
                # Handle failed transactions (log them or save for further review)
                print("Cleaning up transaction payment was not successful")
                payment = Payment.objects.filter(checkoutrequest_id=checkoutrequestid).first()

                payment.is_deleted = True
                payment.deleted_at = timezone.now()
                payment.save()
                print("Successfully cleaned up transaction payment")
                return JsonResponse({"ResultCode": 1, "ResultDesc": "Transaction failed"}, status=400)
                # print("Successfully cleaned up transaction payment")
                # return JsonResponse({"ResultCode": 1, "ResultDesc": "Transaction failed"}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)
def register_mpesa_urls():
    """Registers C2B URLs for Paybill"""
    token = get_mpesa_token()
    if not token:
        return {"error": "Failed to authenticate"}

    url = "https://sandbox.safaricom.co.ke/mpesa/c2b/v1/registerurl"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "ShortCode": settings.MPESA_SHORTCODE,
        "ResponseType": "Completed",  # Completed or Cancelled
        "ConfirmationURL": f"{settings.MPESA_CALLBACK_URL}",
        "ValidationURL": f"{settings.MPESA_VALIDATION_URL}"
    }

    response = requests.post(url, json=payload, headers=headers)
    print("Register URLs response ",json.dumps(response.json(), indent=4))
    return response.json()


@csrf_exempt
def mpesa_confirmation(request):
    """Handles Paybill confirmation callback"""
    if request.method == "POST":
        data = json.loads(request.body)
        print("M-Pesa Confirmation Data:", data)

        transaction = {
            "TransactionID": data.get("TransID"),
            "Amount": data.get("TransAmount"),
            "PaybillNumber": data.get("BusinessShortCode"),
            "PhoneNumber": data.get("MSISDN"),
            "AccountNumber": data.get("BillRefNumber"),
            "TransactionTime": data.get("TransTime")
        }

        # TODO: Save transaction to database

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def mpesa_validation(request):
    """Handles Paybill validation callback"""
    if request.method == "POST":
        data = json.loads(request.body)
        print("M-Pesa Validation Data:", data)

        # Validate transaction (optional)
        # Example: Check if AccountNumber exists in your system

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})  # Accept transaction

    return JsonResponse({"error": "Invalid request"}, status=400)


class MpesaPaymentView(APIView):
    def post(self, request):
        phone_number = request.data.get("phoneNumber")
        amount = request.data.get("amount")

        if not phone_number or not amount:
            return JsonResponse({"error": "Please provide phone number and amount"}, status=400)
        response = lipa_na_mpesa(phone_number, int(float(amount)))
        if response.get("ResponseCode") == "0":
            return JsonResponse({"message": "Payment initiated successfully","response":response}, status=200)
        else:
            return JsonResponse({"error": response}, status=400)
