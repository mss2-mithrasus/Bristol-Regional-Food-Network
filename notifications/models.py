from django.db import models

# Create your models here.
from user_accounts.models import UserAccount


class Notification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        db_column="user_id"
    )
    message = models.TextField()
    type = models.CharField(max_length=100)
    date_created = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        managed = True
        db_table = "notifications"