"""
Custom User Model for Transport System
Supports email-based authentication with role-based access
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from zones.models import Zone   # ✅ NEW IMPORT


class CustomUserManager(BaseUserManager):
    """
    Custom manager for email-based authentication instead of username
    """
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')   # SUPERUSER ALWAYS ADMIN
        extra_fields.setdefault('zone', None)      # SUPERUSER NOT TIED TO ZONE

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    Custom User Model
    - Uses email instead of username for authentication
    - Has role field for access control (passenger, driver, zonal admin, admin)
    """

    username = None  # Remove username field
    email = models.EmailField(unique=True, verbose_name='Email Address')

    # Role-based access control
    ROLE_CHOICES = (
        ('passenger', 'Passenger'),
        ('driver', 'Driver'),
        ('zonal_admin', 'Zonal Admin'),   # ✅ NEW ROLE
        ('admin', 'Admin'),
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='passenger',
        help_text='User role in the system'
    )

    # Assigned zone (for drivers + zonal admins)
    zone = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="Zone for zonal admins and drivers"
    )

    # Set email as the unique identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email & Password are required by default

    # Use custom manager
    objects = CustomUserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email
