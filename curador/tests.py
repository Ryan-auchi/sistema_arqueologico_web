import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestAcessoNaoAutenticado:
    """Usuário sem sessão deve ser redirecionado ao tentar acessar rotas protegidas."""

    def test_fila_redireciona_para_login(self, client):
        response = client.get(reverse("curadoria-fila"))
        assert response.status_code in (302, 403)

    def test_audit_logs_redireciona_para_login(self, client):
        response = client.get(reverse("audit-logs"))
        assert response.status_code in (302, 403)

    def test_audit_detail_redireciona_para_login(self, client):
        response = client.get(reverse("audit-detail", args=["999"]))
        assert response.status_code in (302, 403)

    def test_curadoria_revisao_redireciona_para_login(self, client):
        response = client.get(reverse("curadoria-revisao", args=["999"]))
        assert response.status_code in (302, 403)
