from django.db import models
from django.db import models
from rest_framework.exceptions import ValidationError

class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    subscription_fee = models.DecimalField(max_digits=10, decimal_places=2)
    subscription_plan = models.CharField(
        max_length=10,
        choices=[("monthly", "Monthly"), ("annual", "Annual")],
        default="monthly"
    )
    is_active = models.BooleanField(default=False)
    company_logo = models.FileField(upload_to='media/logo',blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    directors = models.ManyToManyField('core.CustomUser', related_name="owned_companies", blank=True)
    is_deleted = models.BooleanField(default=False)
    date_deleted = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name

class Employee(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    user = models.OneToOneField('core.CustomUser', on_delete=models.CASCADE, related_name="employee_profile")
    position = models.CharField(max_length=255, blank=True, null=True)
    date_employed = models.DateField(blank=True, null=True)
    salary = models.DecimalField(max_digits=255, decimal_places=2, null=True)
    is_deleted = models.BooleanField(default=False)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_branch = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)
    date_deleted = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.user.email} - {self.position}"

class EmployeeCommissionSetting(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="commission_settings")
    service = models.ForeignKey("services.Service", on_delete=models.CASCADE, related_name="employee_commissions")
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Commission percentage for this service"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'service')  # Ensure unique commission per employee-service pair

    def clean(self):
        """
        Ensure the employee and service belong to the same company.
        """
        if self.employee.company != self.service.company:
            raise ValidationError("Employee and service must belong to the same company.")

    def save(self, *args, **kwargs):
        self.clean()  # Run validation before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.user.email} - {self.service.name} ({self.commission_percentage}%)"

class EmployeeCommission(models.Model):
    """Tracks commission payments for a sale item."""
    sale_item = models.ForeignKey('sales_invoices.SaleItem', on_delete=models.CASCADE, related_name='commissions')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='commissions')
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid = models.BooleanField(default=False)
    date_paid = models.DateTimeField(null=True, blank=True)
    date_calculate = models.DateField(auto_now_add=True)

    def calculate_commission(self):
        """Calculates commission dynamically based on the employee and service."""
        if self.sale_item.type != 'service' or not self.sale_item.service:
            return 0

        try:
            setting = EmployeeCommissionSetting.objects.get(
                employee=self.employee,
                service=self.sale_item.service
            )
            return (setting.commission_percentage / 100) * float(self.sale_item.amount)
        except EmployeeCommissionSetting.DoesNotExist:
            return 0  # No commission if no setting exists

    def save(self, *args, **kwargs):
        """Auto-calculate commission before saving."""
        if self.commission_amount is None:
            self.commission_amount = self.calculate_commission()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Paid" if self.paid else "Unpaid"
        return f"{self.sale_item} - {self.employee.full_name} - {self.commission_amount} ({status})"


class EmployeeRemuneration(models.Model):
    REMUNERATION_TYPES = [
        ('Basic Salary','Basic Salary'),
        ('House Allowance', 'House Allowance'),
        ('Commuter Allowance', 'Commuter Allowance'),
        ('Leave Allowance', 'Leave Allowance'),
        ('Bonus', 'Bonus'),
        ('Commission', 'Commission'),
        ('Other', 'Other'),
    ]
    remuneration_type = models.CharField(max_length=20, choices=REMUNERATION_TYPES, default='bonus')
    name = models.CharField(max_length=100, blank=True,null=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,related_name='remunerations')  # Add this field
    amount = models.DecimalField(decimal_places=2,default=0.0,max_digits=20)
    currency = models.CharField(max_length=20,default='Ksh')
    effective_date = models.DateField(help_text="Month this deduction affects (e.g., 2025-04-01)")
    # effective_Year = models.DateField(help_text="Month this deduction affects (e.g., 2025-04-01)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'remuneration_type')

class EmployeeLeave(models.Model):
    LEAVE_TYPES = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('compassionate', 'Compassionate Leave'),
        ('study', 'Study Leave'),
        ('unpaid', 'Unpaid Leave'),
        ('other', 'Other')
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leaves")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey('core.CustomUser', null=True, blank=True, on_delete=models.SET_NULL, related_name='leave_reviews')

    def __str__(self):
        return f"{self.employee.user.username} - {self.leave_type} ({self.start_date} to {self.end_date})"

    class Meta:
        ordering = ['-created_at']
class EmployeeDeduction(models.Model):
    DEDUCTION_TYPES = [
        ('penalty', 'Penalty'),
        ('loan', 'Loan'),
        ('advance', 'Salary Advance'),
        ('other', 'Other')
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="deductions")
    deduction_type = models.CharField(max_length=20, choices=DEDUCTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    effective_month = models.DateField(help_text="Month this deduction affects (e.g., 2025-04-01)")
    end_month = models.DateField(blank=True,null=True,help_text="Month this deduction ends (e.g., 2025-04-01)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.user.username} - {self.deduction_type} ({self.amount})"

    class Meta:
        ordering = ['-created_at']

class EmployeePaymentDetails(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payment_details')
    salary_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()

    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('mobile_money', 'Mobile Money'),
        ]
    )
    account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    payment_month = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 13)])
    payment_year = models.PositiveIntegerField()
    deductions = models.JSONField(default=dict)  # e.g., {"tax": 1000, "nssf": 200, "nhif": 300}
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    is_paid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_year', '-payment_month', '-payment_date']
        verbose_name = 'Employee Payment Detail'
        verbose_name_plural = 'Employee Payment Details'
        unique_together = ('employee', 'payment_month', 'payment_year')  # Prevent duplicate salary entries

    def __str__(self):
        return f"{self.employee.user.name} - {self.payment_month}/{self.payment_year}"

    def calculate_net_pay(self):
        total_deductions = sum(self.deductions.values()) if self.deductions else 0
        return self.salary_amount - total_deductions

    def save(self, *args, **kwargs):
        # Automatically calculate net pay before saving
        self.net_pay = self.calculate_net_pay()
        super().save(*args, **kwargs)

class EmployeePayroll(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls')
    payment_month = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 13)])
    payment_year = models.PositiveIntegerField()
    payment_date = models.DateField(auto_now_add=True)

    # Earnings
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    allowances = models.JSONField(default=dict)  # {"housing": 10000, "transport": 5000}
    bonuses = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Deductions
    deductions = models.JSONField(default=dict)  # {"paye": 1000, "nssf": 200, "nhif": 300}

    # Payment Info
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('mobile_money', 'Mobile Money'),
            ('cash', 'Cash'),
        ]
    )
    account_number = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)

    # Status
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'payment_month', 'payment_year')
        ordering = ['-payment_year', '-payment_month']

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.payment_month}/{self.payment_year}"

    # Calculation Methods
    def get_total_allowances(self):
        return sum(self.allowances.values()) if self.allowances else 0

    def get_total_deductions(self):
        return sum(self.deductions.values()) if self.deductions else 0

    def get_gross_pay(self):
        return self.basic_salary + self.get_total_allowances() + self.bonuses

    def get_net_pay(self):
        return self.get_gross_pay() - self.get_total_deductions()

    def generate_payslip(self):
        return {
            "employee": self.employee.get_full_name(),
            "month": self.payment_month,
            "year": self.payment_year,
            "basic_salary": self.basic_salary,
            "allowances": self.allowances,
            "bonuses": self.bonuses,
            "gross_pay": self.get_gross_pay(),
            "deductions": self.deductions,
            "net_pay": self.get_net_pay(),
            "payment_method": self.payment_method,
            "account_number": self.account_number,
            "bank_name": self.bank_name,
            "payment_date": self.payment_date,
            "is_paid": self.is_paid,
        }


class Payslip(models.Model):
    payroll = models.OneToOneField(EmployeePayroll, on_delete=models.CASCADE)
    generated_on = models.DateTimeField(auto_now_add=True)
    pdf_path = models.CharField(max_length=255, blank=True)  # Optional path to PDF

    def __str__(self):
        return f"Payslip for {self.payroll}"
