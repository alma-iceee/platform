from django.db import connection
from django.db.utils import OperationalError
from django.http import JsonResponse


def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
