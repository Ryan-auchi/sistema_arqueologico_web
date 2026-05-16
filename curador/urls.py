from django.urls import path

from .views import audit_detail, audit_logs, curadoria_fila, curadoria_revisao

urlpatterns = [
    path("audit-logs/", audit_logs, name="audit-logs"),
    path("audit-detail/<str:audit_id>/", audit_detail, name="audit-detail"),
    path("curadoria/fila/", curadoria_fila, name="curadoria-fila"),
    path("curadoria/revisao/<str:curadoria_id>/", curadoria_revisao, name="curadoria-revisao"),
]
