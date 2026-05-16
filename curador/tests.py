import pytest
from django.urls import reverse

from pesquisa.models import Usuario


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


class TestStatusLabel:
    def test_pendente(self):
        from curador.views import _status_label

        assert _status_label("pendente") == "Pendente"

    def test_aprovado(self):
        from curador.views import _status_label

        assert _status_label("aprovado") == "Aprovado"

    def test_rejeitado(self):
        from curador.views import _status_label

        assert _status_label("rejeitado") == "Rejeitado"

    def test_valor_desconhecido_retorna_capitalizado(self):
        from curador.views import _status_label

        assert _status_label("outro") == "Outro"


class TestFieldLabel:
    def test_campo_conhecido(self):
        from curador.views import _field_label

        assert _field_label("nome_bem") == "Nome do bem"

    def test_campo_desconhecido_formata_com_espacos(self):
        from curador.views import _field_label

        assert _field_label("campo_novo") == "Campo Novo"


class TestTruncate:
    def test_texto_curto_nao_trunca(self):
        from curador.views import _truncate

        assert _truncate("Pedra Furada") == "Pedra Furada"

    def test_texto_longo_trunca(self):
        from curador.views import _truncate

        texto = "A" * 100
        resultado = _truncate(texto)
        assert len(resultado) <= 72
        assert resultado.endswith("...")

    def test_none_retorna_string_vazia(self):
        from curador.views import _truncate

        assert _truncate(None) == ""


class TestJsonOrText:
    def test_none_retorna_vazio(self):
        from curador.views import _json_or_text

        assert _json_or_text(None) == ""

    def test_dict_retorna_json(self):
        from curador.views import _json_or_text

        result = _json_or_text({"a": 1})
        assert '"a"' in result

    def test_lista_retorna_json(self):
        from curador.views import _json_or_text

        result = _json_or_text(["x", "y"])
        assert "x" in result

    def test_string_retorna_string(self):
        from curador.views import _json_or_text

        assert _json_or_text("texto") == "texto"


# ─────────────────────────────────────────────────────────────────────────────
# Controle de acesso
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAcessoNaoAutenticado:
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


@pytest.mark.django_db
class TestAcessoColetor:
    """Coletor autenticado não deve acessar rotas de curadoria."""

    def test_fila_redireciona_coletor(self, client):
        coletor = Usuario.objects.create_user(
            email="coletor@test.com",
            password="senha123",
            nome="Coletor Teste",
            perfil=Usuario.PerfilUsuario.COLETOR,
        )
        client.force_login(coletor)
        response = client.get(reverse("curadoria-fila"))
        assert response.status_code == 302
