from django.conf import settings  # Best practice for referencing User
from django.db import models # type: ignore
from django.contrib.auth.models import User # type: ignore
from django.urls import reverse # type: ignore
from django.core.validators import MinLengthValidator # type: ignore
from django.contrib.auth.models import User # type: ignore
import uuid
import os

# Create your models here.

class Entity(models.Model):
    entity = models.CharField(max_length=40)
    users = models.ManyToManyField(User)

    def __str__(self):
        return self.entity

class Period(models.Model):
    period = models.CharField(max_length=7, validators=[MinLengthValidator(7)])

    def __str__(self):
        return self.period

class Status(models.Model):
    option = models.CharField(max_length=40)

    def __str__(self):
        return self.option


class Gldetail(models.Model):
    entity = models.ForeignKey(
        Entity, on_delete=models.CASCADE, default=None, blank=True, null=True)
    period = models.ForeignKey(
        Period, on_delete=models.CASCADE, default=None, blank=True, null=True)
    glnum = models.CharField(max_length=12, validators=[
                             MinLengthValidator(12)], verbose_name='GL Number')
    gldesc = models.CharField(max_length=40, verbose_name='GL Description')
    glamt = models.DecimalField(
        max_digits=11, decimal_places=2, verbose_name='GL Amount')

    status = models.ForeignKey(Status, on_delete=models.CASCADE, default=1)
    updated_at = models.DateTimeField(auto_now=True)

    username = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='usernames',
        editable=False,
        verbose_name="Last Modified By"
    )

    created_by = models.ForeignKey(
        User, related_name='created_gldetails', on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(
        User, related_name='updated_gldetails', on_delete=models.SET_NULL, null=True, blank=True)

    def get_absolute_url(self):
        return reverse('gldetail-update', kwargs={'pk': self.pk})

    def __str__(self):
        return f"{self.entity} - {self.period} - {self.glnum}"

    class Meta:
        unique_together = (('entity', 'period', 'glnum'),)


def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = "%s.%s" % (uuid.uuid4(), ext)
    return os.path.join('documents/', filename)


class EntryType(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name

class Glpost(models.Model):
    gldetail = models.ForeignKey(Gldetail, on_delete=models.CASCADE, default=None, blank=True, null=True)
    jdate = models.CharField(max_length=10, validators=[MinLengthValidator(10)], verbose_name='Date')
    jref = models.CharField(max_length=6, validators=[MinLengthValidator(6)], verbose_name='Reference')
    jamt = models.DecimalField(max_digits=11, decimal_places=2, verbose_name='Amount')
    jdesc = models.CharField(max_length=20, verbose_name='Description')
    jattach = models.FileField(upload_to=get_file_path, verbose_name='Support Attachment', default=None, blank=True, null=True)
    entry_type = models.ForeignKey(
        EntryType, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(
        User, related_name='created_glposts', on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(
        User, related_name='updated_glposts', on_delete=models.SET_NULL, null=True, blank=True)
    
    username = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='postusernames',
        editable=False,
        verbose_name="Last Modified By",
        null=True,
        blank=True
    )
    def __str__(self):
        return self.jref
    
    
class GlReconciliation(models.Model):
    gldetail = models.OneToOneField(Gldetail, on_delete=models.CASCADE)
    beginning_balance = models.DecimalField(max_digits=11, decimal_places=2)
    ending_balance = models.DecimalField(max_digits=11, decimal_places=2)
    adjustments = models.DecimalField(
        max_digits=11, decimal_places=2, default=0.00)
    explanation = models.TextField(blank=True, null=True)
    prepared_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='reconciliations_prepared')
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='reconciliations_reviewed')
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.ForeignKey(Status, on_delete=models.CASCADE, default=1)

    def difference(self):
        return (self.beginning_balance + self.adjustments) - self.ending_balance

    def is_balanced(self):
        return self.difference() == 0

    def __str__(self):
        return f"Reconciliation for {self.gldetail}"



