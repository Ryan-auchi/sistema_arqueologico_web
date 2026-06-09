from unittest.mock import patch

import pytest
from django.urls import reverse

from conftest import SITE_FAKE

ARTIGO_BEM_FAKE = {
    "id": "vin-001",
    "artigo_id": "art-001",
    "titulo": "Artigo Teste",
    "doi": "10.1000/xyz",
    "autores": "Silva",
    "tipo_mencao": "citacao",
    "trecho_relevante": "Trecho",
}


@pytest.mark.django_db
class TestPesquisaMapa:
    def test_retorna_200_com_api_ok(self, client):
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(SITE_FAKE,)):
            response = client.get(reverse("pesquisa-mapa"))
        assert response.status_code == 200

    def test_retorna_200_sem_api(self, client):
        from api_client.client import ApiError

        with patch("pesquisa.views.fetch_all_bens_materiais", side_effect=ApiError("offline")):
            response = client.get(reverse("pesquisa-mapa"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestPesquisaLista:
    def test_retorna_200_com_api_ok(self, client):
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(SITE_FAKE,)):
            response = client.get(reverse("pesquisa-lista"))
        assert response.status_code == 200

    def test_retorna_200_sem_api(self, client):
        from api_client.client import ApiError

        with patch("pesquisa.views.fetch_all_bens_materiais", side_effect=ApiError("offline")):
            response = client.get(reverse("pesquisa-lista"))
        assert response.status_code == 200

    def test_filtro_por_uf(self, client):
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(SITE_FAKE,)):
            response = client.get(reverse("pesquisa-lista") + "?state=PI")
        assert response.status_code == 200


@pytest.mark.django_db
class TestApiSites:
    def test_retorna_json_com_resultados(self, client):
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(SITE_FAKE,)):
            response = client.get(reverse("api-sitios"))
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["count"] == 1

    def test_retorna_json_vazio_sem_api(self, client):
        from api_client.client import ApiError

        with patch("pesquisa.views.fetch_all_bens_materiais", side_effect=ApiError("offline")):
            response = client.get(reverse("api-sitios"))
        assert response.status_code == 200
        assert response.json()["count"] == 0


@pytest.mark.django_db
class TestSiteDetail:
    def _mocks_basicos(self):
        """Retorna patch combinado para os mocks mínimos do site_detail."""
        return [
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
        ]

    def test_get_site_existente_retorna_200(self, client):
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
        ):
            response = client.get(reverse("pesquisa-detalhe", args=["abc-123"]))
        assert response.status_code == 200

    def test_get_site_inexistente_retorna_404(self, client):
        from api_client.client import ApiError

        with patch("pesquisa.views.fetch_bem_material", side_effect=ApiError("not found", 404)):
            response = client.get(reverse("pesquisa-detalhe", args=["nao-existe"]))
        assert response.status_code == 404

    def test_get_carrega_artigos_e_colaboradores_no_contexto(self, client):
        colaborador_fake = {"id": "u1", "nome": "Colaborador", "email": "col@test.com", "classificacao": "estudante", "origem": "coleta", "total_contribuicoes": 1}
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[ARTIGO_BEM_FAKE]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[colaborador_fake]),
        ):
            response = client.get(reverse("pesquisa-detalhe", args=["abc-123"]))
        assert response.status_code == 200
        assert len(response.context["artigos"]) == 1
        assert len(response.context["colaboradores"]) == 1

    def test_get_curador_recebe_is_curador_or_admin_true(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_curadores", return_value=[]),
        ):
            response = client.get(reverse("pesquisa-detalhe", args=["abc-123"]))
        assert response.context["is_curador_or_admin"] is True

    def test_post_toggle_publicado_chama_api(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_curadores", return_value=[]),
            patch("pesquisa.views.toggle_publicado_bem_material", return_value=SITE_FAKE) as mock_toggle,
            patch("pesquisa.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "toggle_publicado", "publicado": "0"},
            )
        mock_toggle.assert_called_once()
        assert response.status_code == 302

    def test_post_remover_vinculo_chama_api(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_curadores", return_value=[]),
            patch("pesquisa.views.remover_vinculo_artigo") as mock_remover,
            patch("pesquisa.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "remover_vinculo", "vinculo_id": "vin-001"},
            )
        mock_remover.assert_called_once_with("vin-001")
        assert response.status_code == 302

    def test_post_excluir_bem_curador_chama_api(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_curadores", return_value=[]),
            patch("pesquisa.views.excluir_bem_material") as mock_excluir,
            patch("pesquisa.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "excluir_bem"},
            )
        mock_excluir.assert_called_once_with("abc-123")
        assert response.status_code == 302

    def test_post_submeter_artigo_chama_api(self, client, coletor_user):
        client.force_login(coletor_user)
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
            patch("pesquisa.views.submeter_artigo", return_value={}) as mock_submeter,
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {
                    "action": "submeter_artigo",
                    "doi": "10.1000/test",
                    "titulo": "Artigo Teste",
                    "autores": "Silva",
                    "tipo_mencao": "citacao",
                },
            )
        mock_submeter.assert_called_once()
        assert response.status_code == 302


@pytest.mark.django_db
class TestApiDOI:
    def test_get_com_doi_valido_retorna_artigo(self, client):
        artigo_mock = {"id": "art-001", "titulo": "Artigo Encontrado", "doi": "10.1000/xyz"}
        with patch("pesquisa.views.buscar_artigo_por_doi", return_value=artigo_mock):
            response = client.get(reverse("api-artigo-doi") + "?doi=10.1000/xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["artigo"]["titulo"] == "Artigo Encontrado"

    def test_get_artigo_nao_encontrado_retorna_null(self, client):
        with patch("pesquisa.views.buscar_artigo_por_doi", return_value=None):
            response = client.get(reverse("api-artigo-doi") + "?doi=10.9999/inexistente")
        assert response.status_code == 200
        assert response.json()["artigo"] is None

    def test_get_artigo_nao_encontrado_por_doi_retorna_null(self, client):
        # buscar_artigo_por_doi já captura ApiError internamente e retorna None;
        # o mock simula esse comportamento retornando None diretamente.
        with patch("pesquisa.views.buscar_artigo_por_doi", return_value=None):
            response = client.get(reverse("api-artigo-doi") + "?doi=10.0000/qualquer")
        assert response.status_code == 200
        assert response.json()["artigo"] is None
