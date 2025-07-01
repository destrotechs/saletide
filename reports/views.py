from django.contrib.admin import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # optional
from sales_invoices.models import Sale,SaleItem
from sales_invoices.serializers import DashboardInsightsSerializer
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from collections import defaultdict
import calendar
from django.db.models import Count, Q
from datetime import timedelta, datetime
from core.permissions import IsCompanyActive

class DashboardInsightsView(APIView):
    permission_classes = [IsAuthenticated,IsCompanyActive]  # optional

    def get(self, request, company_id):
        data = Sale.objects.dashboard_insights(company_id=company_id)
        top_data = get_top_services_and_products(company_id)
        serializer = DashboardInsightsSerializer(data)
        # Get chart data
        chart_data = get_sales_data_by_company(company_id)

        # Combine both into one response
        response_data = {
            **serializer.data,  # Unpack serializer data
            'top_data': top_data  # Add chart data
        }

        return Response(response_data)
class ChartDataView(APIView):
    permission_classes = [IsAuthenticated,IsCompanyActive]  # optional
    def get(self,request,company_id):
        time_filter = request.query_params.get('time_filter',None)
        start_date = request.query_params.get('startDate',None)
        end_date = request.query_params.get('endDate',None)
        if not company_id:
            return  Response({"error":"There was an error fetching company data, try again"},status=400)
        chart_data = get_sales_data_by_company(company_id=company_id,time_filter=time_filter,start_date=start_date,end_date=end_date)

        return Response(chart_data,status=200)

class TopDataProductsAndServicesView(APIView):
    permission_classes = [IsAuthenticated,IsCompanyActive]  # optional

    def get(self, request, company_id):
        time_filter = request.query_params.get('time_filter', "this_month")
        limit = request.query_params.get('limit', 4)
        top_data = get_top_services_and_products(company_id,time_filter,int(limit))
        return Response(top_data,status=200)

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

def get_sales_data_by_company(company_id, time_filter='7_days', start_date=None, end_date=None):
    now = timezone.now()

    # Parse manual dates if provided
    start_date = parse_date(start_date) if start_date else None
    end_date = parse_date(end_date) if end_date else None

    # Predefined filters
    if time_filter == 'today':
        start_date = end_date = now.date()
    elif time_filter == '7_days':
        start_date = now - timedelta(days=7)
        end_date = now
    elif time_filter == '1_month':
        first_day_this_month = timezone.datetime(now.year, now.month, 1).date()
        last_day_last_month = first_day_this_month - timedelta(days=1)
        start_date = timezone.datetime(last_day_last_month.year, last_day_last_month.month, 1).date()
        end_date = last_day_last_month
    elif time_filter == 'current_year':
        start_date = timezone.datetime(now.year, 1, 1).date()
        end_date = timezone.datetime(now.year, 12, 31).date()

    elif time_filter == '1_year':
        start_date = now - timedelta(days=365)
        end_date = now
    elif time_filter == 'current_year':
        start_date = timezone.datetime(now.year, 1, 1).date()
        end_date = timezone.datetime(now.year, 12, 31).date()

    elif time_filter == 'last_year':
        start_date = timezone.datetime(now.year - 1, 1, 1).date()
        end_date = timezone.datetime(now.year - 1, 12, 31).date()

    elif time_filter == 'all':
        start_date = end_date = None
    # elif not (start_date and end_date):
    #     # Default to current year
    #     start_date = timezone.datetime(now.year, 1, 1)
    #     end_date = timezone.datetime(now.year, 12, 31)

    filters = {
        'sale__is_deleted': False,
        'sale__company_id': company_id,
    }
    if start_date:
        filters['sale__date__gte'] = start_date
    if end_date:
        filters['sale__date__lte'] = end_date

    # Choose time grouping
    if time_filter == 'today' or (end_date and (end_date - start_date).days <= 7):
        trunc_func = TruncDay
        label_format = "%b %d"
    elif time_filter in ['1_month', '7_days'] or (end_date and (end_date - start_date).days <= 31):
        trunc_func = TruncWeek
        label_format = "Week of %b %d"
    else:
        trunc_func = TruncMonth
        label_format = "%b %Y"

    # Query sales
    items = SaleItem.objects.filter(**filters).annotate(
        period=trunc_func('sale__date')
    ).values('period', 'type').annotate(
        total_sales=Sum('total')
    ).order_by('period')

    # Organize data
    data = defaultdict(lambda: {'service': 0, 'product': 0})
    labels = []

    for item in items:
        key = item['period'].strftime(label_format)
        data[key][item['type']] = float(item['total_sales'])
        if key not in labels:
            labels.append(key)

    # Build chart format
    chart_data = []
    for label in labels:
        chart_data.append({
            'period': label,
            'service': data[label]['service'],
            'product': data[label]['product'],
        })

    return chart_data

def get_top_services_and_products(company_id, period='this_month', limit=3):
    today = timezone.now().date()

    # Date range filter based on the period
    if period == 'today':
        date_filter = Q(sale__date=today)
    elif period == 'this_month':
        first_day = today.replace(day=1)
        date_filter = Q(sale__date__gte=first_day)
    elif period == 'this_year':
        first_day = today.replace(month=1, day=1)
        date_filter = Q(sale__date__gte=first_day)
    else:
        # Default to 'this_month' if an unknown period is provided
        first_day = today.replace(day=1)
        date_filter = Q(sale__date__gte=first_day)

    # Common filter for all queries
    base_filter = Q(sale__company_id=company_id, sale__is_deleted=False) & date_filter

    # Top Services
    top_services = (
        SaleItem.objects
        .filter(base_filter, type='service', service__isnull=False)
        .values('service__id', 'service__name')
        .annotate(sale_count=Count('id'))
        .order_by('-sale_count')[:limit]
    )

    # Top Products
    top_products = (
        SaleItem.objects
        .filter(base_filter, type='product', product__isnull=False)
        .values('product__id', 'product__name')
        .annotate(sale_count=Count('id'))
        .order_by('-sale_count')[:limit]
    )

    return {
        'top_services': list(top_services),
        'top_products': list(top_products)
    }