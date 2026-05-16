from unittest.mock import patch

import pytest
from django.urls import reverse

SITE_FAKE = {
    "id": "abc-123",
    "nome_bem": "Sítio Pedra Furada",
    "codigo_iphan": "PI-0001",
    "natureza": "arqueologico",
    "tipo": "sitio",
    "uf": "PI",
    "municipio": "São Raimundo Nonato",
    "latitude": -8.48,
    "longitude": -42.60,
    "publicado": True,
    "geojson": None,
    "midias": [],
    "responsavel": {},
    "nomes_populares": "",
    "meios_acesso": "",
    "artefatos": [],
    "descricao_atualizacao": "",
    "cep": "",
    "endereco": "",
    "ano_registro": 2020,
    "criado_em": None,
    "atualizado_em": None,
    "deletado_em": None,
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
