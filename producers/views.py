from django.shortcuts import render
from django.http import HttpResponse
from django.db import connection

def db_test(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = cursor.fetchall()
        return HttpResponse(f"Database OK — Tables: {tables}")
    except Exception as e:
        return HttpResponse(f"Database ERROR: {e}")