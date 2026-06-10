from unittest.mock import patch

import pytest
from django.urls import reverse

from conftest import SITE_FAKE

# ─────────────────────────────────────────────────────────────────────────────
# catalog.py — funções puras (sem DB nem API)
# ─────────────────────────────────────────────────────────────────────────────


class TestCatalogFilteredSites:
    def test_sem_filtros_retorna_todos(self):
        from pesquisa.catalog import SITES, filtered_sites
        result = filtered_sites({})
        assert len(result) == len(SITES)

    def test_filtro_conservation(self):
        from pesquisa.catalog import filtered_sites
        result = filtered_sites({"conservation": "excellent"})
        assert all(s["conservation"] == "excellent" for s in result)

    def test_filtro_state(self):
        from pesquisa.catalog import filtered_sites
        result = filtered_sites({"state": "Piauí"})
        assert all(s["state"] == "Piauí" for s in result)
        assert len(result) >= 1

    def test_filtro_query_nome(self):
        from pesquisa.catalog import filtered_sites
        result = filtered_sites({"q": "capivara"})
        assert len(result) >= 1
        assert any("Capivara" in s["name"] or "capivara" in s["name"].lower() for s in result)

    def test_filtro_sem_resultado(self):
        from pesquisa.catalog import filtered_sites
        result = filtered_sites({"conservation": "excellent", "state": "Amazonas"})
        assert result == []


class TestCatalogSerializeSite:
    def test_serialize_retorna_campos_esperados(self):
        from pesquisa.catalog import SITES, serialize_site
        result = serialize_site(SITES[0])
        assert "name" in result
        assert "latitude" in result
        assert "longitude" in result
        assert "badge" in result
        # campos que NÃO devem aparecer na serialização simples
        assert "gallery" not in result


# ─────────────────────────────────────────────────────────────────────────────
# pesquisa/models.py — UsuarioManager
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUsuarioManager:
    def test_create_user_sem_email_levanta_erro(self):
        from pesquisa.models import Usuario
        with pytest.raises(ValueError, match="email"):
            Usuario.objects.create_user(email="", nome="Teste", password="123")

    def test_create_user_sem_nome_levanta_erro(self):
        from pesquisa.models import Usuario
        with pytest.raises(ValueError, match="nome"):
            Usuario.objects.create_user(email="x@test.com", nome="", password="123")

    def test_create_superuser_cria_com_is_staff_true(self):
        from pesquisa.models import Usuario
        su = Usuario.objects.create_superuser(
            email="super@test.com",
            nome="Super",
            password="supersenha",
        )
        assert su.is_staff is True
        assert su.is_superuser is True

    def test_create_superuser_sem_is_staff_levanta_erro(self):
        from pesquisa.models import Usuario
        with pytest.raises(ValueError, match="is_staff"):
            Usuario.objects.create_superuser(
                email="super2@test.com",
                nome="Super2",
                password="supersenha",
                is_staff=False,
            )

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
class TestApiSitesFiltros:
    """Filtragem aplicada via _site_filter — testada via endpoint JSON."""

    def _get(self, client, params=""):
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(SITE_FAKE,)):
            return client.get(reverse("api-sitios") + params)

    def test_filtro_municipality(self, client):
        data = self._get(client, "?municipality=São Raimundo Nonato").json()
        assert data["count"] == 1

    def test_filtro_municipality_sem_resultado(self, client):
        data = self._get(client, "?municipality=CidadeInexistente").json()
        assert data["count"] == 0

    def test_filtro_nature_encontra(self, client):
        data = self._get(client, "?nature=arqueologico").json()
        assert data["count"] == 1

    def test_filtro_nature_nao_encontra(self, client):
        data = self._get(client, "?nature=historico").json()
        assert data["count"] == 0

    def test_filtro_type_encontra(self, client):
        data = self._get(client, "?type=sitio").json()
        assert data["count"] == 1

    def test_filtro_q_nome_encontra(self, client):
        data = self._get(client, "?q=Pedra+Furada").json()
        assert data["count"] == 1

    def test_filtro_q_sem_resultado(self, client):
        data = self._get(client, "?q=xyz_inexistente").json()
        assert data["count"] == 0

    def test_filtro_ano_min_inclui(self, client):
        data = self._get(client, "?ano_min=2019").json()
        assert data["count"] == 1

    def test_filtro_ano_min_exclui(self, client):
        data = self._get(client, "?ano_min=2021").json()
        assert data["count"] == 0

    def test_filtro_ano_max_inclui(self, client):
        data = self._get(client, "?ano_max=2021").json()
        assert data["count"] == 1

    def test_filtro_ano_max_exclui(self, client):
        data = self._get(client, "?ano_max=2019").json()
        assert data["count"] == 0

    def test_filtro_artefato_nao_encontra(self, client):
        # SITE_FAKE não tem artefatos
        data = self._get(client, "?artefato=ceramica").json()
        assert data["count"] == 0

    def test_show_unpublished_inclui_nao_publicados(self, client):
        site_priv = {**SITE_FAKE, "id": "priv-1", "publicado": False, "published": False}
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(site_priv,)):
            data = client.get(reverse("api-sitios") + "?show_unpublished=1").json()
        assert data["count"] == 1

    def test_site_nao_publicado_filtrado_por_padrao(self, client):
        site_priv = {**SITE_FAKE, "id": "priv-2", "publicado": False, "published": False}
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(site_priv,)):
            data = client.get(reverse("api-sitios")).json()
        assert data["count"] == 0

    def test_filtro_state_mismatch_exclui_site(self, client):
        # SITE_FAKE tem uf=PI; filtrar por SP deve excluir
        data = self._get(client, "?state=SP").json()
        assert data["count"] == 0

    def test_filtro_type_mismatch_exclui_site(self, client):
        data = self._get(client, "?type=rupestre").json()
        assert data["count"] == 0

    def test_filtro_artefato_encontra_quando_presente(self, client):
        site_com_artefato = {**SITE_FAKE, "id": "art-s1", "artefatos": ["cerâmica", "lítico"]}
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(site_com_artefato,)):
            data = client.get(reverse("api-sitios") + "?artefato=cerâmica").json()
        assert data["count"] == 1

    def test_filtro_geometry_populado_no_site(self, client):
        site_geo = {**SITE_FAKE, "id": "geo-1", "geojson": {"type": "Point", "coordinates": [-42.60, -8.48]}}
        with patch("pesquisa.views.fetch_all_bens_materiais", return_value=(site_geo,)):
            data = client.get(reverse("api-sitios")).json()
        assert data["count"] == 1


def _P_BEM():
    return patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE)


def _P_AUD():
    return patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[])


def _P_ART():
    return patch("pesquisa.views.fetch_artigos_por_bem", return_value=[])


def _P_COL():
    return patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[])


def _P_CUR():
    return patch("pesquisa.views.fetch_curadores", return_value=[])


@pytest.mark.django_db
class TestSiteDetailErrorPaths:
    """Caminhos de erro nas POST actions do site_detail."""

    def test_toggle_publicado_api_error_retorna_404(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            _P_BEM(), _P_AUD(), _P_ART(), _P_COL(), _P_CUR(),
            patch("pesquisa.views.toggle_publicado_bem_material", side_effect=ApiError("erro", 500)),
            patch("pesquisa.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "toggle_publicado", "publicado": "0"},
            )
        assert response.status_code == 404

    def test_submeter_artigo_com_artigo_id_passa_id_no_payload(self, client, coletor_user):
        client.force_login(coletor_user)
        with (
            _P_BEM(), _P_AUD(), _P_ART(), _P_COL(),
            patch("pesquisa.views.submeter_artigo", return_value={}) as mock_sub,
        ):
            client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {
                    "action": "submeter_artigo",
                    "doi": "10.1000/test",
                    "titulo": "Artigo",
                    "autores": "Silva",
                    "tipo_mencao": "citacao",
                    "artigo_id": "art-existente",
                },
            )
        payload_enviado = mock_sub.call_args[0][0]
        assert payload_enviado.get("artigo_id") == "art-existente"

    def test_submeter_artigo_api_error_redireciona(self, client, coletor_user):
        from api_client.client import ApiError
        client.force_login(coletor_user)
        with (
            _P_BEM(), _P_AUD(), _P_ART(), _P_COL(),
            patch("pesquisa.views.submeter_artigo", side_effect=ApiError("falha")),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "submeter_artigo", "titulo": "X", "tipo_mencao": "citacao"},
            )
        assert response.status_code == 302

    def test_remover_vinculo_api_error_redireciona(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            _P_BEM(), _P_AUD(), _P_ART(), _P_COL(), _P_CUR(),
            patch("pesquisa.views.remover_vinculo_artigo", side_effect=ApiError("falha")),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "remover_vinculo", "vinculo_id": "vin-001"},
            )
        assert response.status_code == 302

    def test_atualizar_curador_responsavel_sucesso(self, client, curador_user):
        client.force_login(curador_user)
        with (
            _P_BEM(), _P_AUD(), _P_ART(), _P_COL(), _P_CUR(),
            patch("pesquisa.views.atualizar_curador_responsavel", return_value=SITE_FAKE) as mock_atualizar,
            patch("pesquisa.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "atualizar_curador_responsavel", "curador_responsavel_id": "cur-001"},
            )
        mock_atualizar.assert_called_once_with("abc-123", "cur-001")
        assert response.status_code == 302

    def test_atualizar_curador_responsavel_api_error_redireciona(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            _P_BEM(), _P_AUD(), _P_ART(), _P_COL(), _P_CUR(),
            patch("pesquisa.views.atualizar_curador_responsavel", side_effect=ApiError("falha")),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "atualizar_curador_responsavel", "curador_responsavel_id": ""},
            )
        assert response.status_code == 302

    def test_excluir_bem_api_error_redireciona(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            _P_BEM(), _P_AUD(), _P_ART(), _P_COL(), _P_CUR(),
            patch("pesquisa.views.excluir_bem_material", side_effect=ApiError("falha")),
            patch("pesquisa.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "excluir_bem"},
            )
        assert response.status_code == 302

    def test_fetch_auditorias_api_error_renderiza_sem_entradas(self, client):
        from api_client.client import ApiError
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", side_effect=ApiError("offline")),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
        ):
            response = client.get(reverse("pesquisa-detalhe", args=["abc-123"]))
        assert response.status_code == 200
        assert response.context["audit_entries"] == []

    def test_fetch_artigos_api_error_renderiza_sem_artigos(self, client):
        from api_client.client import ApiError
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", side_effect=ApiError("offline")),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
        ):
            response = client.get(reverse("pesquisa-detalhe", args=["abc-123"]))
        assert response.status_code == 200
        assert response.context["artigos"] == []

    def test_fetch_colaboradores_api_error_renderiza_com_erro(self, client):
        from api_client.client import ApiError
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", side_effect=ApiError("offline", 503)),
        ):
            response = client.get(reverse("pesquisa-detalhe", args=["abc-123"]))
        assert response.status_code == 200
        assert response.context["colaboradores"] == []

    def test_atualizar_curador_responsavel_coletor_retorna_404(self, client, coletor_user):
        client.force_login(coletor_user)
        with (_P_BEM(), _P_AUD(), _P_ART(), _P_COL()):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "atualizar_curador_responsavel", "curador_responsavel_id": "x"},
            )
        assert response.status_code == 404

    def test_excluir_bem_coletor_retorna_404(self, client, coletor_user):
        client.force_login(coletor_user)
        with (_P_BEM(), _P_AUD(), _P_ART(), _P_COL()):
            response = client.post(
                reverse("pesquisa-detalhe", args=["abc-123"]),
                {"action": "excluir_bem"},
            )
        assert response.status_code == 404

    def test_fetch_curadores_api_error_nao_quebra(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            patch("pesquisa.views.fetch_bem_material", return_value=SITE_FAKE),
            patch("pesquisa.views.fetch_auditorias_for_bem", return_value=[]),
            patch("pesquisa.views.fetch_artigos_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_colaboradores_por_bem", return_value=[]),
            patch("pesquisa.views.fetch_curadores", side_effect=ApiError("offline")),
        ):
            response = client.get(reverse("pesquisa-detalhe", args=["abc-123"]))
        assert response.status_code == 200


@pytest.mark.django_db
class TestApiDOI:
    def test_get_com_doi_valido_retorna_artigo(self, client):
        artigo_mock = {"id": "art-001", "titulo": "Artigo Encontrado", "doi": "10.1000/xyz"}
        with patch("pesquisa.views.buscar_artigo_por_doi", return_value=artigo_mock):
            response = client.get(reverse("api-artigo-doi") + "?doi=10.1000/xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["artigo"]["titulo"] == "Artigo Encontrado"

    def test_get_sem_doi_retorna_null(self, client):
        with patch("pesquisa.views.buscar_artigo_por_doi", return_value=None):
            response = client.get(reverse("api-artigo-doi"))
        assert response.status_code == 200
        assert response.json()["artigo"] is None

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
