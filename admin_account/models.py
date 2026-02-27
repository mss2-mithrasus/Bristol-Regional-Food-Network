from django.db import models

# Create your models here.


class AdminSecurity(models.Model):
    security_log_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()  # FK placeholder (later → ForeignKey to User)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "admin_security"


class AdminFinancialReport(models.Model):
    financial_report_id = models.AutoField(primary_key=True)
    date_range_start = models.DateField()
    date_range_end = models.DateField()
    total_commission = models.DecimalField(max_digits=12, decimal_places=2)
    total_orders = models.IntegerField()

    class Meta:
        managed = True
        db_table = "admin_financial_report"