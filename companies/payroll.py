import os
from django.template.loader import render_to_string
from django.http import JsonResponse
from weasyprint import HTML
from io import BytesIO
from datetime import datetime
from django.conf import settings
from .models import Company, Employee, EmployeeRemuneration


def calculate_paye(taxable_income):
    tax = 0
    bands = [
        (24000, 0.10),
        (8333, 0.25),
        (467667, 0.30),
        (300000, 0.325),
        (float('inf'), 0.35),
    ]

    for band_limit, rate in bands:
        if taxable_income > band_limit:
            tax += band_limit * rate
            taxable_income -= band_limit
        else:
            tax += taxable_income * rate
            break

    tax -= 2400  # personal relief
    return max(tax, 0)


def generate_payroll(request):
    company_id = request.POST.get("company_id")
    month_str = request.POST.get("month")  # Format: YYYY-MM
    month = datetime.strptime(month_str, "%Y-%m")

    company = Company.objects.get(id=company_id)
    employees = Employee.objects.filter(company=company, is_deleted=False)

    payroll_data = []

    for employee in employees:
        remunerations = EmployeeRemuneration.objects.filter(employee=employee)
        gross_salary = sum(r.amount for r in remunerations)

        nssf = min(gross_salary * 0.06, 1080)
        shif = max(gross_salary * 0.0275, 300)
        ahl = gross_salary * 0.015

        taxable_income = gross_salary - (nssf + shif + ahl)
        paye = calculate_paye(taxable_income)

        net_salary = gross_salary - (nssf + shif + ahl + paye)

        payroll_data.append({
            'name': employee.user.get_full_name(),
            'gross': gross_salary,
            'nssf': nssf,
            'shif': shif,
            'ahl': ahl,
            'paye': paye,
            'net': net_salary,
        })

    # Render HTML to string
    html_string = render_to_string("payroll_template.html", {
        "company": company,
        "month": month.strftime("%B %Y"),
        "payroll": payroll_data,
    })

    # Create directory if not exists
    output_dir = os.path.join(settings.MEDIA_ROOT, 'payrolls')
    os.makedirs(output_dir, exist_ok=True)

    filename = f"payroll_{company.id}_{month.strftime('%Y_%m')}.pdf"
    file_path = os.path.join(output_dir, filename)

    # Write PDF to file
    HTML(string=html_string).write_pdf(file_path)

    # Build absolute URL
    file_url = request.build_absolute_uri(os.path.join(settings.MEDIA_URL, 'payrolls', filename))

    return JsonResponse({'status': 'success', 'pdf_url': file_url})
