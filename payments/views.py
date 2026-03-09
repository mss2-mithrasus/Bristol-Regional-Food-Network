from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from django.db import connection


def payments_test(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = cursor.fetchall()
        return HttpResponse(f"Payments DB OK — Tables: {tables}")
    except Exception as e:
        return HttpResponse(f"Payments DB ERROR: {e}")