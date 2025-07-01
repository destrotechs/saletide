from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.db import models
from companies.models import Company

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email field is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'SuperAdmin')
        return self.create_user(email, password, **extra_fields)


class Role(models.TextChoices):
    SUPER_ADMIN = 'SuperAdmin', 'SuperAdmin'
    COMPANY_OWNER = 'CompanyOwner', 'CompanyOwner'
    COMPANY_ADMIN = 'CompanyAdmin', 'CompanyAdmin'
    COMPANY_MANAGER = 'CompanyManager', 'CompanyManager'
    COMPANY_EMPLOYEE = 'CompanyEmployee', 'CompanyEmployee'


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name="users"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.COMPANY_EMPLOYEE)

    # Overriding groups and user_permissions to avoid reverse accessor clashes
    groups = models.ManyToManyField(Group, related_name="customuser_groups", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="customuser_permissions", blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} - {self.role}"