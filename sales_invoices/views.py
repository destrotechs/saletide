import decimal
import os
from ast import literal_eval
from rest_framework.views import APIView
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_date
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK
from weasyprint import HTML

from companies.models import Company
from customers.models import Customer
from services.models import Service
from .models import Sale, Invoice,SaleItemRequirement,Payment,PaymentSale,PaymentInvoice
from .serializers import SaleSerializer, InvoiceSerializer,PaymentSerializer
from core.permissions import IsSuperAdmin, IsCompanyOwnerOrAdmin
from inventory.models import InventoryItem
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
import datetime
from rest_framework.exceptions import NotFound
from core.permissions import IsCompanyActive
from django.utils import timezone
User = get_user_model()
import logging

logger = logging.getLogger("csm")

from rest_framework import viewsets
from .models import Sale, SaleItem, SaleItemEmployee
from .serializers import SaleSerializer, SaleItemSerializer, SaleItemEmployeeSerializer
from rest_framework.permissions import IsAuthenticated


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated,IsCompanyActive]

    def get_queryset(self):
        user = self.request.user
        customer = self.request.query_params.get('customer', None)
        start_date = self.request.query_params.get('startDate', None)
        end_date = self.request.query_params.get('endDate', None)

        queryset = self.queryset

        if customer:
            queryset = queryset.filter(customer=customer)

        # Date filtering
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        items_data = data.pop('items', [])
        user = request.user

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()

        for item_data in items_data:
            employees = item_data.pop('employees', [])

            _product = InventoryItem.objects.filter(pk=item_data.get('product')).first()
            _service = Service.objects.filter(pk=item_data.get('service')).first()

            item_data['product'] = _product
            item_data['service'] = _service

            item = SaleItem.objects.create(sale=sale, **item_data)

            if _product:
                current_quantity = _product.quantity
                if decimal.Decimal(item_data.get('quantity'))>current_quantity:
                    return Response({"error":"The requested sale quantity exceeds the available quantity"},status=400)

                quantity_diff = decimal.Decimal(item_data.get('quantity'))
                _product.reduce_stock(abs(quantity_diff), user=user, notes=f"Stock reduction from a sale {sale.id}")


            for emp_id in employees:
                SaleItemEmployee.objects.create(sale_item=item, employee_id=emp_id)

        return Response(self.get_serializer(sale).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        sale = self.get_object()
        if sale.is_invoiced:
            return Response({"error": "You cannot delete a sale linked to an invoice"}, status=HTTP_400_BAD_REQUEST)

        invoices = InvoiceSerializer(sale.invoices.all(),many=True)

        if invoices.data:
            return Response({"error":"You cannot delete a sale linked to an invoice"},status=HTTP_400_BAD_REQUEST)

        sale.is_deleted = True
        sale.deleted_at = timezone.now()
        sale.save()

        return Response({"message": "Sale deleted successfully"}, status=HTTP_200_OK)

    @action(detail=False,methods=['get'],url_path='generate-sales-report')
    def generate_sales_report(self,request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        # Query Sales and SaleItems based on the date range
        sales = Sale.objects.filter(date__range=[start_date, end_date], is_deleted=False)

        # Prepare data for the report
        report_data = []

        total_amount = total_tax = grand_total = 0

        for sale in sales:
            for item in sale.items.all():
                item_total = item.amount * item.quantity  # amount per item x quantity
                item_tax = item_total * (item.product.tax_rate/100)  if item.product else (item.service.tax_rate/100)
                total_amount += item_total
                total_tax += item_tax
                grand_total += item_total + item_tax

                report_data.append({
                    'date': sale.date,
                    'customer': sale.customer.full_name if sale.customer else '',
                    'vehicle': sale.vehicle.plate_number if sale.vehicle else '',
                    'item_type': 'Service' if item.type == 'service' else 'Product',
                    'item_name': item.service.name if item.type == 'service' else item.product.name,
                    'quantity': item.quantity,
                    'amount': item.amount,
                    'item_total': item_total,
                    'item_tax': item_tax,
                    'item_grand_total': item_total + item_tax,
                })

        # Generate the PDF content (HTML format)
        html_content = render_to_string('sales-report.html', {
            'report_data': report_data,
            'total_amount': total_amount,
            'total_tax': total_tax,
            'grand_total': grand_total,
            'start_date': start_date,
            'end_date': end_date,
            'company': request.user.company,
            'generated_at': timezone.now()
        })

        # Save the generated PDF file
        pdf_file_path = os.path.join(settings.MEDIA_ROOT, f"sales_report_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf")
        HTML(string=html_content).write_pdf(pdf_file_path)

        # Return the absolute URL of the generated PDF
        report_url = request.build_absolute_uri(
            os.path.join(settings.MEDIA_URL, os.path.basename(pdf_file_path))
        )
        return Response({"report_url": report_url})


class SaleItemViewSet(viewsets.ModelViewSet):
    queryset = SaleItem.objects.all()
    serializer_class = SaleItemSerializer
    permission_classes = [IsAuthenticated,IsCompanyActive]


class SaleItemEmployeeViewSet(viewsets.ModelViewSet):
    queryset = SaleItemEmployee.objects.all()
    serializer_class = SaleItemEmployeeSerializer
    permission_classes = [IsAuthenticated,IsCompanyActive]

class InvoiceViewSet(viewsets.ModelViewSet):
    """
    View for managing invoices.
    """
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated,IsCompanyActive]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SuperAdmin":
            return Invoice.objects.all()
        return Invoice.objects.filter(company=user.company, is_deleted=False)

    def create(self, request, *args, **kwargs):
        user = request.user
        data = request.data.copy()
        print("data",data)
        # Extract sale IDs from nested items
        items = request.data.get("sales", [])
        if not items:
            return Response({"error": "Invoice must have items."}, status=status.HTTP_400_BAD_REQUEST)

        sales_ids = []
        for item in items:
            if not item or "sale_id" not in item:
                return Response({"error": "Each item must include a valid sale object with an ID."},
                                status=status.HTTP_400_BAD_REQUEST)
            sales_ids.append(item["sale_id"])

        # Authorization
        allowed_roles = {"SuperAdmin", "CompanyOwner", "CompanyAdmin"}
        if user.role not in allowed_roles:
            return Response({"error": "You are not authorized to add invoices."}, status=status.HTTP_403_FORBIDDEN)

        # Remove nested fields not needed directly in the invoice
        data.pop("sales", None)
        data.pop("totals", None)
        data['sales']=sales_ids

        # Inject company
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            invoice = serializer.save(company=user.company)

            # Associate sales
            sales = Sale.objects.filter(id__in=sales_ids, is_deleted=False, company=user.company)
            if sales.count() != len(sales_ids):
                return Response({"error": "Some sales are either deleted or not part of your company."},
                                status=status.HTTP_400_BAD_REQUEST)

            invoice.sales.set(sales)
            for sale in sales:
                sale.is_invoiced = True
                sale.save()

            return Response(
                {"message": "Invoice created successfully", "data": InvoiceSerializer(invoice).data},
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='add-sale')
    def add_sale(self, request, pk=None):
        """
        Add a sale to an existing invoice.
        """
        invoice = self.get_object()  # Get the current invoice
        sale_id = request.data.get("sale_id")
        try:
            sale = Sale.objects.get(id=sale_id)
        except Sale.DoesNotExist:
            return Response({"error": "Sale not found."}, status=status.HTTP_404_NOT_FOUND)

        user = self.request.user

        if sale.is_deleted:
            raise PermissionDenied(f"Cannot add a deleted sale with ID {sale.id} to an invoice.")
        if sale.company != invoice.company:
            raise PermissionDenied(f"Cannot add a sale from a different company to this invoice.")

        invoice.sales.add(sale)  # Add the sale to the invoice
        return Response({
            "message": "Sale added to invoice successfully.",
            "invoice": InvoiceSerializer(invoice).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='remove-sale')
    def remove_sale(self, request, pk=None):
        """
        Remove a sale from an existing invoice.
        """
        invoice = self.get_object()  # Get the current invoice
        sale_id = request.data.get("sale_id")
        try:
            sale = Sale.objects.get(id=sale_id)
        except Sale.DoesNotExist:
            return Response({"error": "Sale not found."}, status=status.HTTP_404_NOT_FOUND)

        if sale not in invoice.sales.all():
            return Response({"error": "Sale is not associated with this invoice."}, status=status.HTTP_400_BAD_REQUEST)

        invoice.sales.remove(sale)  # Remove the sale from the invoice
        return Response({
            "message": "Sale removed from invoice successfully.",
            "invoice": InvoiceSerializer(invoice).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='generate-invoice-pdf')
    def generate_invoice_pdf(self, request, pk=None):
        try:
            invoice = self.get_object()

            # Authorization check
            if request.user.company != invoice.company:
                return Response({"error": "You are not authorized to view this invoice"}, status=403)

            # Serialize invoice data
            invoice_data = InvoiceSerializer(invoice).data
            customer = Customer.objects.get(pk=invoice_data['customer'])
            company = Company.objects.get(pk=invoice_data['company'])

            # Process sale items
            sales = []
            total_amount = decimal.Decimal('0.00')
            subtotal_amount = decimal.Decimal('0.00')
            tax_total_amount = decimal.Decimal('0.00')
            discount_total_amount = decimal.Decimal('0.00')

            for sale in invoice_data.get('sale_details', []):
                sale_total = decimal.Decimal('0.00')
                sale_subtotal = decimal.Decimal('0.00')
                sale_tax = decimal.Decimal('0.00')
                sale_discount = decimal.Decimal('0.00')

                for item in sale.get('sale_items', []):
                    # Ensure all relevant fields are Decimal objects
                    amount = decimal.Decimal(str(item.get('amount', '0.00')))
                    quantity = decimal.Decimal(str(item.get('quantity', '1.00')))
                    subtotal = decimal.Decimal(str(item.get('subtotal', '0.00')))
                    tax_amount = decimal.Decimal(str(item.get('tax_amount', '0.00')))
                    discount_amount = decimal.Decimal(str(item.get('discount_amount', '0.00')))
                    item_total = decimal.Decimal(str(item.get('total', '0.00')))

                    # Validate total calculation for consistency
                    calculated_total = subtotal + tax_amount - discount_amount
                    if abs(calculated_total - item_total) > decimal.Decimal('0.01'):
                        # If there's a discrepancy, use the calculated value
                        item_total = calculated_total
                        item['total'] = str(item_total)

                    # Add to sale totals
                    sale_subtotal += subtotal
                    sale_tax += tax_amount
                    sale_discount += discount_amount
                    sale_total += item_total

                    # Format financial values for display
                    item['amount_formatted'] = '{:.2f}'.format(amount)
                    item['subtotal_formatted'] = '{:.2f}'.format(subtotal)
                    item['tax_amount_formatted'] = '{:.2f}'.format(tax_amount)
                    item['discount_amount_formatted'] = '{:.2f}'.format(discount_amount)
                    item['total_formatted'] = '{:.2f}'.format(item_total)

                # Add sale totals
                sale['sale_subtotal'] = sale_subtotal
                sale['sale_tax'] = sale_tax
                sale['sale_discount'] = sale_discount
                sale['sale_total'] = sale_total

                # Format sale totals for display
                sale['sale_subtotal_formatted'] = '{:.2f}'.format(sale_subtotal)
                sale['sale_tax_formatted'] = '{:.2f}'.format(sale_tax)
                sale['sale_discount_formatted'] = '{:.2f}'.format(sale_discount)
                sale['sale_total_formatted'] = '{:.2f}'.format(sale_total)

                # Add to invoice totals
                subtotal_amount += sale_subtotal
                tax_total_amount += sale_tax
                discount_total_amount += sale_discount
                total_amount += sale_total

                sales.append(sale)

            # Render HTML
            html_content = render_to_string('invoice_template.html', {
                'invoice': invoice_data,
                'sales': sales,
                'subtotal_amount': subtotal_amount,
                'tax_total_amount': tax_total_amount,
                'discount_total_amount': discount_total_amount,
                'total_amount': total_amount,
                'customer': customer,
                'company': company,
            })

            # Generate PDF
            pdf_file = HTML(string=html_content).write_pdf()
            pdf_url = self._save_pdf_file(invoice.invoice_number, pdf_file, request)

            return Response({'invoice_pdf_url': pdf_url})

        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=404)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    def _save_pdf_file(self, invoice_number, pdf_file, request):
        """Save PDF to media directory and return its absolute URL."""
        filename = f'invoice_{invoice_number}.pdf'
        invoice_dir = os.path.join(settings.MEDIA_ROOT, 'invoices')
        os.makedirs(invoice_dir, exist_ok=True)

        path = os.path.join(invoice_dir, filename)
        with open(path, 'wb') as f:
            f.write(pdf_file)

        relative_url = os.path.join(settings.MEDIA_URL, 'invoices', filename)
        return request.build_absolute_uri(relative_url)


class PaymentView(APIView):
    permission_classes = [IsAuthenticated,IsCompanyActive]
    def post(self, request):
        try:
            data = request.data
            print("Request data", data)

            invoice_ids = data.get('invoices', [])
            sale_ids = data.get('sales', [])
            payment_ids = data.get('payments', [])

            if not payment_ids:
                # Create a single payment if no existing payments provided
                payment = Payment.objects.create(
                    amount_paid=data['receivedAmount'],
                    date_paid=data['createDate'],
                    payment_method=data['paymentMethod'],
                    transaction_id=data.get('receiptId') or data.get('reference'),
                    remarks=data.get('note', '')
                )
                self.link_payment(payment, invoice_ids, sale_ids)
                return Response({"payment": PaymentSerializer(payment).data}, status=status.HTTP_200_OK)

            # Link existing payments to provided sales/invoices
            linked_payments = []
            for payment_id in payment_ids:
                try:
                    payment = Payment.objects.get(pk=payment_id)
                    self.link_payment(payment, invoice_ids, sale_ids)
                    linked_payments.append(payment)
                except Payment.DoesNotExist:
                    continue  # Or return error if strict validation is needed

            return Response({"payments": PaymentSerializer(linked_payments, many=True).data}, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def link_payment(self, payment, invoice_ids, sale_ids):
        """Link a payment to multiple invoices and/or sales"""
        if invoice_ids:
            for id in invoice_ids:
                try:
                    invoice = Invoice.objects.get(pk=id)
                    PaymentInvoice.objects.get_or_create(payment=payment, invoice=invoice)
                    invoice.status = 'Paid'
                    invoice.save()
                except Invoice.DoesNotExist:
                    continue

        if sale_ids:
            for id in sale_ids:
                try:
                    sale = Sale.objects.get(pk=id)
                    PaymentSale.objects.get_or_create(payment=payment, sale=sale)
                    sale.status = 'Paid'
                    sale.save()
                except Sale.DoesNotExist:
                    continue


    def get(self, request):
        try:
            payment = Payment.objects.all()
            serializer = PaymentSerializer(payment,many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)