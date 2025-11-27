from django.db import models

class Zone(models.Model):
    """
    Zone Model (Zonal areas like Taliparamba, Payyannur, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    district = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Zone"
        verbose_name_plural = "Zones"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"
