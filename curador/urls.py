from django.urls import path

from .views import (
    artigo_detalhe,
    artigos_lista,
    audit_detail,
    audit_logs,
    curadoria_fila,
    curadoria_revisao,
    excluir_artigo_view,
    restaurar_auditoria_view,
)

urlpatterns = [
    path("audit-logs/", audit_logs, name="audit-logs"),
    path("audit-detail/<str:audit_id>/", audit_detail, name="audit-detail"),
    path("audit-detail/<str:audit_id>/restaurar/", restaurar_auditoria_view, name="restaurar-auditoria"),
    path("curadoria/fila/", curadoria_fila, name="curadoria-fila"),
    path("curadoria/revisao/<str:curadoria_id>/", curadoria_revisao, name="curadoria-revisao"),
    path("artigos/", artigos_lista, name="artigos-lista"),
    path("artigos/<str:artigo_id>/", artigo_detalhe, name="artigo-detalhe"),
    path("artigos/<str:artigo_id>/excluir/", excluir_artigo_view, name="excluir-artigo"),
]
