from django.db import models
from companies.models import Company

class Report(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    report_type = models.CharField(max_length=255)
    generated_at = models.DateTimeField(auto_now_add=True)
    file_path = models.FileField(upload_to="reports/")

    def __str__(self):
        return f"Report {self.id} - {self.report_type}"
