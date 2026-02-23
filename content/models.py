from django.db import models
from django.conf import settings

# Create your models here.

class Article(models.Model):
    article_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    body= models.TextField()
    image = models.CharField(max_length=500, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    
    
    class Meta:
        managed = True
        db_table = "content"
        
        
    def __str__(self):
        return self.title
