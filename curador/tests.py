from unittest.mock import patch

import pytest
from django.urls import reverse

from conftest import (
    AUDIT_ALTERACAO_FAKE,
    AUDIT_EXCLUSAO_FAKE,
    AUDIT_INSERCAO_FAKE,
    CURADORIA_ARTIGO_EXISTENTE_FAKE,
    CURADORIA_ARTIGO_NOVO_FAKE,
    CURADORIA_COLETA_EXISTENTE_FAKE,
    CURADORIA_COLETA_NOVA_FAKE,
    PAGINACAO_VAZIA,
    SITE_FAKE,
)

# Dicts normalizados para mocks de fetch_artigo_admin / list_artigos_admin
# (simulam a saída de _normalize_artigo, que tem total_vinculos em vez de vinculos_count)
_ARTIGO_NORM = {
    "id": "art-001",
    "titulo": "Artigo sobre Pedra Furada",
    "doi": "10.1000/xyz123",
    "autores": "Silva, João",
    "ano_publicacao": 2022,
    "periodico": "Revista Arqueológica",
    "idioma": "pt",
    "resumo": "Um estudo.",
    "link_acesso": "https://example.com",
    "verificado": True,
    "total_vinculos": 1,
    "created_at": None,
    "updated_at": "2026-06-01",
    "adicionado_por": {"nome": "Curador Teste"},
    "vinculos": [
        {
            "id": "vin-001",
            "tipo_mencao": "citacao",
            "trecho_relevante": "Trecho importante.",
            "bem_material_id": "abc-123",
            "bem_material": {
                "id": "abc-123",
                "nome_bem": "Sítio Pedra Furada",
                "codigo_iphan": "PI-0001",
                "municipio": "São Raimundo Nonato",
                "uf": "PI",
            },
        }
    ],
}

_ARTIGO_A = {
    "id": "a1",
    "titulo": "Alfa",
    "total_vinculos": 5,
    "ano_publicacao": 2020,
    "updated_at": "2026-01-01",
}
_ARTIGO_B = {
    "id": "a2",
    "titulo": "Zeta",
    "total_vinculos": 2,
    "ano_publicacao": 2023,
    "updated_at": "2026-06-01",
}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers puros
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


class TestNamespace:
    def test_dict_plano_vira_namespace(self):
        from curador.views import _namespace
        ns = _namespace({"a": 1, "b": "dois"})
        assert ns.a == 1
        assert ns.b == "dois"

    def test_dict_aninhado_vira_namespace_recursivo(self):
        from curador.views import _namespace
        ns = _namespace({"outer": {"inner": 42}})
        assert ns.outer.inner == 42

    def test_lista_de_dicts_vira_lista_de_namespaces(self):
        from curador.views import _namespace
        result = _namespace([{"x": 1}, {"x": 2}])
        assert result[0].x == 1
        assert result[1].x == 2


class TestHaversineKm:
    def test_mesmas_coordenadas_retornam_zero(self):
        from curador.views import _haversine_km
        assert _haversine_km(-8.48, -42.60, -8.48, -42.60) == pytest.approx(0.0, abs=0.01)

    def test_recife_sao_paulo_distancia_conhecida(self):
        from curador.views import _haversine_km
        # Recife (-8.05, -34.88) ↔ São Paulo (-23.55, -46.63) ≈ 2130 km em linha reta
        dist = _haversine_km(-8.05, -34.88, -23.55, -46.63)
        assert 2000 < dist < 2300

    def test_distancia_simetrica(self):
        from curador.views import _haversine_km
        d1 = _haversine_km(-8.48, -42.60, -23.55, -46.63)
        d2 = _haversine_km(-23.55, -46.63, -8.48, -42.60)
        assert d1 == pytest.approx(d2, abs=0.001)

    def test_distancia_sempre_positiva(self):
        from curador.views import _haversine_km
        assert _haversine_km(-8.0, -42.0, -8.5, -42.5) > 0


class TestSitiosProximos:
    def test_site_dentro_do_raio_incluido(self):
        from curador.views import _sitios_proximos
        site_prox = {**SITE_FAKE, "id": "s1", "latitude": -8.50, "longitude": -42.62}
        with patch("curador.views.fetch_all_bens_materiais", return_value=(site_prox,)):
            result = _sitios_proximos(-8.48, -42.60)
        assert len(result) == 1
        assert result[0]["id"] == "s1"

    def test_site_fora_do_raio_excluido(self):
        from curador.views import _sitios_proximos
        site_longe = {**SITE_FAKE, "id": "s2", "latitude": -23.55, "longitude": -46.63}
        with patch("curador.views.fetch_all_bens_materiais", return_value=(site_longe,)):
            result = _sitios_proximos(-8.48, -42.60, raio_km=10)
        assert len(result) == 0

    def test_excluir_id_remove_site_mesmo_proximo(self):
        from curador.views import _sitios_proximos
        site_prox = {**SITE_FAKE, "id": "s1", "latitude": -8.50, "longitude": -42.62}
        with patch("curador.views.fetch_all_bens_materiais", return_value=(site_prox,)):
            result = _sitios_proximos(-8.48, -42.60, excluir_id="s1")
        assert len(result) == 0

    def test_retorna_no_maximo_5_mais_proximos(self):
        from curador.views import _sitios_proximos
        sites = [
            {**SITE_FAKE, "id": f"s{i}", "latitude": -8.48 + i * 0.01, "longitude": -42.60}
            for i in range(10)
        ]
        with patch("curador.views.fetch_all_bens_materiais", return_value=tuple(sites)):
            result = _sitios_proximos(-8.48, -42.60)
        assert len(result) <= 5

    def test_api_error_retorna_lista_vazia(self):
        from api_client.client import ApiError
        from curador.views import _sitios_proximos
        with patch("curador.views.fetch_all_bens_materiais", side_effect=ApiError("offline")):
            result = _sitios_proximos(-8.48, -42.60)
        assert result == []


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

    def test_artigos_lista_redireciona_para_login(self, client):
        response = client.get(reverse("artigos-lista"))
        assert response.status_code in (302, 403)

    def test_artigo_detalhe_redireciona_para_login(self, client):
        response = client.get(reverse("artigo-detalhe", args=["999"]))
        assert response.status_code in (302, 403)

    def test_excluir_artigo_redireciona_para_login(self, client):
        response = client.post(reverse("excluir-artigo", args=["999"]))
        assert response.status_code in (302, 403)

    def test_restaurar_auditoria_redireciona_para_login(self, client):
        response = client.post(reverse("restaurar-auditoria", args=["999"]))
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestAcessoColetor:
    """Coletor autenticado não deve acessar rotas de curadoria."""

    def test_fila_redireciona_coletor(self, client, coletor_user):
        client.force_login(coletor_user)
        response = client.get(reverse("curadoria-fila"))
        assert response.status_code == 302

    def test_artigos_lista_redireciona_coletor(self, client, coletor_user):
        client.force_login(coletor_user)
        response = client.get(reverse("artigos-lista"))
        assert response.status_code == 302

    def test_artigo_detalhe_redireciona_coletor(self, client, coletor_user):
        client.force_login(coletor_user)
        response = client.get(reverse("artigo-detalhe", args=["999"]))
        assert response.status_code == 302

    def test_audit_logs_redireciona_coletor(self, client, coletor_user):
        client.force_login(coletor_user)
        response = client.get(reverse("audit-logs"))
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# curadoria_fila
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCuradoriaFila:
    def test_get_retorna_200_com_page_obj(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_NOVA_FAKE,)):
            response = client.get(reverse("curadoria-fila"))
        assert response.status_code == 200
        assert response.context["page_obj"] is not None

    def test_get_api_error_retorna_200_com_lista_vazia(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", side_effect=ApiError("offline")):
            response = client.get(reverse("curadoria-fila"))
        assert response.status_code == 200
        assert list(response.context["page_obj"]) == []

    def test_get_filtro_q_retorna_200(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_NOVA_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?q=Pedra")
        assert response.status_code == 200

    def test_get_filtro_tipo_coleta(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_NOVA_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?tipo=coleta")
        assert response.status_code == 200

    def test_get_filtro_destino_novo_sitio(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_NOVA_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?destino=novo_sitio")
        assert response.status_code == 200

    def test_get_filtro_conflito_sim_filtra_corretamente(self, client, curador_user):
        client.force_login(curador_user)
        # coleta nova sem conflito (bem_material={}) → não aparece com conflito=sim
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_NOVA_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?conflito=sim")
        assert response.status_code == 200
        # deve retornar lista vazia pois CURADORIA_COLETA_NOVA_FAKE não tem conflito
        assert response.context["total_filtrado"] == 0

    def test_get_filtro_tipo_artigo(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_ARTIGO_NOVO_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?tipo=artigo")
        assert response.status_code == 200

    def test_get_filtro_destino_sitio_existente(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_EXISTENTE_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?destino=sitio_existente")
        assert response.status_code == 200
        assert response.context["total_filtrado"] == 1

    def test_get_filtro_conflito_nao(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_NOVA_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?conflito=nao")
        assert response.status_code == 200

    def test_get_filtro_meu_responsavel(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_all_curadorias", return_value=(CURADORIA_COLETA_EXISTENTE_FAKE,)):
            response = client.get(reverse("curadoria-fila") + "?meu_responsavel=1")
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# curadoria_revisao — coleta
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCuradoriaRevisaoColeta:
    def _mocks_get(self, curadoria=None, bens=()):
        """Mocks padrão para GET de revisão de coleta."""
        return [
            patch("curador.views.fetch_curadoria", return_value=curadoria or CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.fetch_curadores", return_value=[]),
            patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)),
            patch("curador.views.fetch_all_bens_materiais", return_value=bens),
        ]

    def test_get_retorna_200_com_comparisons(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.fetch_curadores", return_value=[]),
            patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)),
            patch("curador.views.fetch_all_bens_materiais", return_value=()),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-001"]))
        assert response.status_code == 200
        assert "comparisons" in response.context

    def test_get_com_sitios_proximos_no_contexto(self, client, curador_user):
        client.force_login(curador_user)
        site_prox = {**SITE_FAKE, "id": "s-prox", "latitude": -8.50, "longitude": -42.62}
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.fetch_curadores", return_value=[]),
            patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)),
            patch("curador.views.fetch_all_bens_materiais", return_value=(site_prox,)),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-001"]))
        assert response.status_code == 200
        assert len(response.context["sitios_proximos"]) >= 1

    def test_nome_de_sitio_proximo_nao_fecha_o_script(self, client, curador_user):
        client.force_login(curador_user)
        malicioso = {
            **SITE_FAKE,
            "id": "s-mal",
            "latitude": -8.50,
            "longitude": -42.62,
            "nome_bem": "</script><script>alert(1)</script>",
        }
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.fetch_curadores", return_value=[]),
            patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)),
            patch("curador.views.fetch_all_bens_materiais", return_value=(malicioso,)),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-001"]))

        html = response.content.decode()
        assert response.status_code == 200
        assert "</script><script>alert(1)" not in html
        assert "\\u003C/script\\u003E" in html

    def test_get_mostra_artefatos_fotos_e_nomes_da_coleta(self, client, curador_user):
        """P17: a API manda relações do modelo (listas de dicts); a revisão mostra os nomes e as fotos."""
        client.force_login(curador_user)
        coleta = {
            **CURADORIA_COLETA_EXISTENTE_FAKE["coleta"],
            "dados_coletados": {"nomes_populares": "Toca da Onça"},
            "artefato_tipos": [
                {"artefato_tipo": {"nome": "Cerâmica"}},
                {"novo_tipo": True, "descricao_nova": "Contas de vidro", "artefato_tipo": {"nome": "Outros"}},
            ],
            "midias": [{"url": "https://fotos.example/1.jpg"}, {"url": "javascript:alert(1)"}],
        }
        curadoria = {
            **CURADORIA_COLETA_EXISTENTE_FAKE,
            "coleta": coleta,
            "bem_material": {**SITE_FAKE, "nomes_populares": [{"nome": "Pedra Furada"}]},
        }
        with (
            patch("curador.views.fetch_curadoria", return_value=curadoria),
            patch("curador.views.fetch_curadores", return_value=[]),
            patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)),
            patch("curador.views.fetch_all_bens_materiais", return_value=()),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-003"]))

        incoming = response.context["incoming_data"]
        assert incoming["artefatos"] == ["Cerâmica", "Contas de vidro"]
        assert incoming["fotos"] == ["https://fotos.example/1.jpg"]
        nomes = next(c for c in response.context["comparisons"] if c["field_name"] == "nomes_populares")
        assert (nomes["incoming_value"], nomes["official_value"]) == ("Toca da Onça", "Pedra Furada")
        html = response.content.decode()
        assert 'src="https://fotos.example/1.jpg"' in html
        assert "javascript:alert" not in html
        assert "unsplash" not in html

    def test_get_curadoria_nao_encontrada_retorna_404(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.fetch_curadoria", side_effect=ApiError("not found", 404)):
            response = client.get(reverse("curadoria-revisao", args=["nao-existe"]))
        assert response.status_code == 404

    def test_post_rejeitar_chama_api_e_redireciona(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.update_curadoria_avaliacao", return_value={}) as mock_update,
            patch("curador.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-001"]),
                {"action": "rejeitar", "observacao": "Dados incompletos"},
            )
        mock_update.assert_called_once()
        payload = mock_update.call_args[0][1]
        assert payload["status"] == "rejeitado"
        assert response.status_code == 302
        assert reverse("curadoria-fila") in response["Location"]

    def test_post_aprovar_sem_bem_material_cria_sitio(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.update_curadoria_avaliacao", return_value={}) as mock_update,
            patch("curador.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-001"]),
                {"action": "aprovar_mesclar", "selected_fields": "[]", "published_selected": "0"},
            )
        payload = mock_update.call_args[0][1]
        assert payload["acao_resultante"] == "criarSitio"
        assert response.status_code == 302

    def test_post_acao_desconhecida_redireciona_de_volta(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-001"]),
                {"action": "acao_invalida"},
            )
        assert response.status_code == 302
        assert "cur-001" in response["Location"]

    def test_post_api_error_redireciona_com_mensagem(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.update_curadoria_avaliacao", side_effect=ApiError("falha")),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-001"]),
                {"action": "rejeitar"},
            )
        assert response.status_code == 302
        assert "cur-001" in response["Location"]

    def test_post_aprovar_com_selected_fields_envia_campos(self, client, curador_user):
        import json as _json
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.update_curadoria_avaliacao", return_value={}) as mock_update,
            patch("curador.views.invalidate_bens_cache"),
        ):
            client.post(
                reverse("curadoria-revisao", args=["cur-001"]),
                {
                    "action": "aprovar_mesclar",
                    "selected_fields": _json.dumps(["nome_bem"]),
                    "published_selected": "0",
                },
            )
        payload = mock_update.call_args[0][1]
        assert "campos" in payload
        assert "nome_bem" in payload["campos"]

    def test_get_list_auditorias_api_error_ainda_renderiza(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.fetch_curadores", return_value=[]),
            patch("curador.views.list_auditorias", side_effect=ApiError("offline")),
            patch("curador.views.fetch_all_bens_materiais", return_value=()),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-001"]))
        assert response.status_code == 200

    def test_post_aprovar_com_bem_material_atualiza_sitio(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_EXISTENTE_FAKE),
            patch("curador.views.update_curadoria_avaliacao", return_value={}) as mock_update,
            patch("curador.views.invalidate_bens_cache"),
        ):
            client.post(
                reverse("curadoria-revisao", args=["cur-003"]),
                {
                    "action": "aprovar_mesclar",
                    "selected_fields": "[]",
                    "published_selected": "0",
                    "bem_material_id": "abc-123",
                },
            )
        payload = mock_update.call_args[0][1]
        assert payload["acao_resultante"] == "atualizarSitio"
        assert payload["bem_material_id"] == "abc-123"


# ─────────────────────────────────────────────────────────────────────────────
# curadoria_revisao — artigo
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCuradoriaRevisaoArtigo:
    def test_get_artigo_retorna_200(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_ARTIGO_NOVO_FAKE),
            patch("curador.views.fetch_artigos_por_bem", return_value=[]),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-002"]))
        assert response.status_code == 200

    def test_get_vinculo_existente_quando_artigo_ja_cadastrado(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_ARTIGO_EXISTENTE_FAKE),
            patch("curador.views.fetch_artigos_por_bem", return_value=[{"id": "art-001"}]),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-004"]))
        assert response.status_code == 200
        assert response.context["vinculo_existente"] is True

    def test_get_vinculo_nao_existente_quando_artigo_novo(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_ARTIGO_NOVO_FAKE),
            patch("curador.views.fetch_artigos_por_bem", return_value=[]),
        ):
            response = client.get(reverse("curadoria-revisao", args=["cur-002"]))
        assert response.context["vinculo_existente"] is False

    def test_post_aprovar_artigo_redireciona(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_ARTIGO_NOVO_FAKE),
            patch("curador.views.update_curadoria_avaliacao", return_value={}) as mock_update,
            patch("curador.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-002"]),
                {"action": "aprovar_artigo"},
            )
        mock_update.assert_called_once()
        payload = mock_update.call_args[0][1]
        assert payload["status"] == "aprovado"
        assert response.status_code == 302

    def test_post_acao_desconhecida_redireciona(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_ARTIGO_NOVO_FAKE),
            patch("curador.views.fetch_artigos_por_bem", return_value=[]),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-002"]),
                {"action": "acao_invalida"},
            )
        assert response.status_code == 302

    def test_post_api_error_redireciona_com_mensagem(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_ARTIGO_NOVO_FAKE),
            patch("curador.views.update_curadoria_avaliacao", side_effect=ApiError("falha")),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-002"]),
                {"action": "aprovar_artigo"},
            )
        assert response.status_code == 302
        assert "cur-002" in response["Location"]

    def test_post_rejeitar_artigo_redireciona(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_ARTIGO_NOVO_FAKE),
            patch("curador.views.update_curadoria_avaliacao", return_value={}) as mock_update,
            patch("curador.views.invalidate_bens_cache"),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-002"]),
                {"action": "rejeitar"},
            )
        payload = mock_update.call_args[0][1]
        assert payload["status"] == "rejeitado"
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# audit_logs
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAuditLogs:
    def test_get_retorna_200_com_page_obj(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([AUDIT_INSERCAO_FAKE], {**PAGINACAO_VAZIA, "total": 1})):
            response = client.get(reverse("audit-logs"))
        assert response.status_code == 200
        assert response.context["page_obj"] is not None

    def test_get_api_error_retorna_200_com_lista_vazia(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", side_effect=ApiError("offline")):
            response = client.get(reverse("audit-logs"))
        assert response.status_code == 200

    def test_get_filtro_criacao_sitio_passa_entidade_tipo_correto(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)) as mock_list:
            client.get(reverse("audit-logs") + "?filtro=criacao_sitio")
        call_kwargs = mock_list.call_args[1]
        assert "App\\Models\\BemMaterial" in call_kwargs.get("entidade_tipo", "")

    def test_get_filtro_responsavel_retorna_200(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([AUDIT_INSERCAO_FAKE], {**PAGINACAO_VAZIA, "total": 1})):
            response = client.get(reverse("audit-logs") + "?responsavel=João")
        assert response.status_code == 200

    def test_get_filtro_q_retorna_200(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([AUDIT_INSERCAO_FAKE], {**PAGINACAO_VAZIA, "total": 1})):
            response = client.get(reverse("audit-logs") + "?q=Pedra")
        assert response.status_code == 200

    def test_get_filtro_artigos_passa_entidade_artigo(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)) as mock_list:
            client.get(reverse("audit-logs") + "?filtro=artigos")
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs.get("entidade_tipo") is not None

    def test_get_filtro_aprovacoes_sitio_passa_entidade_curadoria(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)) as mock_list:
            client.get(reverse("audit-logs") + "?filtro=aprovacoes_sitio")
        call_kwargs = mock_list.call_args[1]
        assert "Curadoria" in (call_kwargs.get("entidade_tipo") or "")

    def test_get_audit_artigo_remocao_label(self, client, curador_user):
        """Auditoria de ArtigoBemMaterial com operação Remoção → label REMOÇÃO-ARTIGO."""
        client.force_login(curador_user)
        audit_artigo = {
            **AUDIT_INSERCAO_FAKE,
            "id": "aud-art-1",
            "entidade_tipo": "App\\Models\\ArtigoBemMaterial",
            "operacao": "Remoção",
            "valor_anterior": {"artigo_titulo": "Artigo X"},
            "valor_novo": None,
        }
        with patch("curador.views.list_auditorias", return_value=([audit_artigo], {**PAGINACAO_VAZIA, "total": 1})):
            response = client.get(reverse("audit-logs"))
        assert response.status_code == 200

    def test_get_audit_artigo_insercao_label(self, client, curador_user):
        """Auditoria de ArtigoBemMaterial com operação Inserção → label VÍNCULO-ARTIGO."""
        client.force_login(curador_user)
        audit_artigo = {
            **AUDIT_INSERCAO_FAKE,
            "id": "aud-art-2",
            "entidade_tipo": "App\\Models\\ArtigoBemMaterial",
            "operacao": "Inserção",
            "valor_novo": {"artigo_titulo": "Artigo Y", "bem_material_id": "bem-1"},
        }
        with patch("curador.views.list_auditorias", return_value=([audit_artigo], {**PAGINACAO_VAZIA, "total": 1})):
            response = client.get(reverse("audit-logs"))
        assert response.status_code == 200

    def test_get_audit_curadoria_rejeicao_label(self, client, curador_user):
        """Auditoria de Curadoria com operação Rejeição → label REJEIÇÃO."""
        client.force_login(curador_user)
        audit_cur = {
            **AUDIT_INSERCAO_FAKE,
            "id": "aud-cur-1",
            "entidade_tipo": "App\\Models\\Curadoria",
            "operacao": "Rejeição",
            "valor_novo": {"nome_bem": "Sítio Rejeitado"},
        }
        with patch("curador.views.list_auditorias", return_value=([audit_cur], {**PAGINACAO_VAZIA, "total": 1})):
            response = client.get(reverse("audit-logs"))
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# audit_detail
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAuditDetail:
    def test_get_insercao_retorna_200_com_restaurar_url(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_auditoria", return_value=AUDIT_INSERCAO_FAKE):
            response = client.get(reverse("audit-detail", args=["aud-001"]))
        assert response.status_code == 200
        assert response.context["restaurar_url"] is not None
        assert response.context["snap_has_anterior"] is False

    def test_get_alteracao_retorna_200_com_snap_has_anterior(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_auditoria", return_value=AUDIT_ALTERACAO_FAKE):
            response = client.get(reverse("audit-detail", args=["aud-002"]))
        assert response.status_code == 200
        assert response.context["restaurar_url"] is not None
        assert response.context["snap_has_anterior"] is True

    def test_get_exclusao_nao_tem_restaurar_url(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_auditoria", return_value=AUDIT_EXCLUSAO_FAKE):
            response = client.get(reverse("audit-detail", args=["aud-003"]))
        assert response.status_code == 200
        assert response.context["restaurar_url"] is None

    def test_get_com_curadoria_vinculada_popula_field_status(self, client, curador_user):
        client.force_login(curador_user)
        audit_com_curadoria = {
            **AUDIT_INSERCAO_FAKE,
            "curadoria_id": "cur-001",
            "valor_novo": {"nome_bem": "Sítio Novo", "uf": "PI", "municipio": "Cidade"},
        }
        with (
            patch("curador.views.fetch_auditoria", return_value=audit_com_curadoria),
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
        ):
            response = client.get(reverse("audit-detail", args=["aud-001"]))
        assert response.status_code == 200

    def test_get_com_curadoria_fetch_error_ainda_renderiza(self, client, curador_user):
        """Se fetch_curadoria falhar, audit_detail deve continuar renderizando."""
        from api_client.client import ApiError
        client.force_login(curador_user)
        audit_com_curadoria = {**AUDIT_INSERCAO_FAKE, "curadoria_id": "cur-001"}
        with (
            patch("curador.views.fetch_auditoria", return_value=audit_com_curadoria),
            patch("curador.views.fetch_curadoria", side_effect=ApiError("not found", 404)),
        ):
            response = client.get(reverse("audit-detail", args=["aud-001"]))
        assert response.status_code == 200

    def test_get_auditoria_tipo_curadoria_rejeicao_renderiza(self, client, curador_user):
        """Auditoria de rejeição (entidade_tipo=Curadoria) popula field_status com rejeitado."""
        client.force_login(curador_user)
        audit_rejeicao = {
            "id": "aud-rej",
            "entidade_tipo": "App\\Models\\Curadoria",
            "entidade_id": "cur-001",
            "curadoria_id": "cur-001",
            "operacao": "Rejeição",
            "meio": "Curadoria",
            "data_hora": "2026-01-04T10:00:00Z",
            "created_at": "2026-01-04T10:00:00Z",
            "valor_anterior": None,
            "valor_novo": {"nome_bem": "Sítio Teste", "uf": "PI", "observacao": "Dados insuficientes"},
            "usuario": {"id": "u1", "name": "Curador", "nome": "Curador"},
            "curadoria": {},
        }
        with (
            patch("curador.views.fetch_auditoria", return_value=audit_rejeicao),
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
        ):
            response = client.get(reverse("audit-detail", args=["aud-rej"]))
        assert response.status_code == 200

    def test_get_auditoria_inexistente_retorna_404(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.fetch_auditoria", side_effect=ApiError("not found", 404)):
            response = client.get(reverse("audit-detail", args=["nao-existe"]))
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# restaurar_auditoria_view
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRestaurarAuditoriaView:
    def test_post_sucesso_redireciona_para_audit_detail(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.restaurar_auditoria", return_value={}) as mock_restaurar,
            patch("curador.views.invalidate_bens_cache"),
        ):
            response = client.post(reverse("restaurar-auditoria", args=["aud-001"]))
        mock_restaurar.assert_called_once_with("aud-001")
        assert response.status_code == 302
        assert "aud-001" in response["Location"]

    def test_post_api_error_redireciona_com_mensagem_de_erro(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.restaurar_auditoria", side_effect=ApiError("falha")):
            response = client.post(reverse("restaurar-auditoria", args=["aud-001"]))
        assert response.status_code == 302
        assert "aud-001" in response["Location"]

    def test_get_nao_e_permitido(self, client, curador_user):
        client.force_login(curador_user)
        response = client.get(reverse("restaurar-auditoria", args=["aud-001"]))
        assert response.status_code == 405

    def test_post_nao_autenticado_redireciona(self, client):
        response = client.post(reverse("restaurar-auditoria", args=["aud-001"]))
        assert response.status_code in (302, 403)


# ─────────────────────────────────────────────────────────────────────────────
# artigos_lista
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestArtigosLista:
    def test_get_retorna_200_com_artigos_no_contexto(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_artigos_admin", return_value=[_ARTIGO_A, _ARTIGO_B]):
            response = client.get(reverse("artigos-lista"))
        assert response.status_code == 200
        assert response.context["total"] == 2

    def test_get_api_error_retorna_200_com_lista_vazia(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.list_artigos_admin", side_effect=ApiError("offline")):
            response = client.get(reverse("artigos-lista"))
        assert response.status_code == 200
        assert response.context["total"] == 0

    def test_sort_titulo_asc_ordena_alfabeticamente(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_artigos_admin", return_value=[_ARTIGO_B, _ARTIGO_A]):
            response = client.get(reverse("artigos-lista") + "?sort=titulo&dir=asc")
        artigos = response.context["artigos"]
        assert artigos[0]["titulo"] == "Alfa"
        assert artigos[1]["titulo"] == "Zeta"

    def test_sort_titulo_desc_inverte_ordem(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_artigos_admin", return_value=[_ARTIGO_A, _ARTIGO_B]):
            response = client.get(reverse("artigos-lista") + "?sort=titulo&dir=desc")
        artigos = response.context["artigos"]
        assert artigos[0]["titulo"] == "Zeta"

    def test_sort_mencoes_desc_ordena_por_vinculos(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_artigos_admin", return_value=[_ARTIGO_B, _ARTIGO_A]):
            response = client.get(reverse("artigos-lista") + "?sort=mencoes&dir=desc")
        artigos = response.context["artigos"]
        assert artigos[0]["total_vinculos"] == 5  # _ARTIGO_A

    def test_sort_ano_asc_ordena_por_publicacao(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_artigos_admin", return_value=[_ARTIGO_B, _ARTIGO_A]):
            response = client.get(reverse("artigos-lista") + "?sort=ano&dir=asc")
        artigos = response.context["artigos"]
        assert artigos[0]["ano_publicacao"] == 2020  # _ARTIGO_A

    def test_sort_invalido_usa_fallback_titulo(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_artigos_admin", return_value=[_ARTIGO_A, _ARTIGO_B]):
            response = client.get(reverse("artigos-lista") + "?sort=invalido")
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# artigo_detalhe
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestArtigoDetalhe:
    def test_get_retorna_200_com_contexto_completo(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_artigo_admin", return_value=_ARTIGO_NORM):
            response = client.get(reverse("artigo-detalhe", args=["art-001"]))
        assert response.status_code == 200
        assert response.context["total_vinculos"] == 1
        assert len(response.context["vinculos"]) == 1

    def test_get_tipo_mencao_label_humanizado(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_artigo_admin", return_value=_ARTIGO_NORM):
            response = client.get(reverse("artigo-detalhe", args=["art-001"]))
        vinculo = response.context["vinculos"][0]
        assert vinculo.tipo_mencao_label == "Citação direta"

    def test_get_artigo_inexistente_retorna_404(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.fetch_artigo_admin", side_effect=ApiError("not found", 404)):
            response = client.get(reverse("artigo-detalhe", args=["nao-existe"]))
        assert response.status_code == 404

    def test_get_excluir_url_aponta_para_rota_correta(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.fetch_artigo_admin", return_value=_ARTIGO_NORM):
            response = client.get(reverse("artigo-detalhe", args=["art-001"]))
        expected_url = reverse("excluir-artigo", args=["art-001"])
        assert response.context["excluir_url"] == expected_url


# ─────────────────────────────────────────────────────────────────────────────
# excluir_artigo_view
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExcluirArtigo:
    def test_post_sucesso_redireciona_para_lista(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.excluir_artigo_admin") as mock_excluir:
            response = client.post(reverse("excluir-artigo", args=["art-001"]))
        mock_excluir.assert_called_once_with("art-001")
        assert response.status_code == 302
        assert reverse("artigos-lista") in response["Location"]

    def test_post_api_error_redireciona_com_mensagem(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with patch("curador.views.excluir_artigo_admin", side_effect=ApiError("falha")):
            response = client.post(reverse("excluir-artigo", args=["art-001"]))
        assert response.status_code == 302
        assert reverse("artigos-lista") in response["Location"]

    def test_get_nao_e_permitido(self, client, curador_user):
        client.force_login(curador_user)
        response = client.get(reverse("excluir-artigo", args=["art-001"]))
        assert response.status_code == 405

    def test_post_nao_autenticado_redireciona(self, client):
        response = client.post(reverse("excluir-artigo", args=["art-001"]))
        assert response.status_code in (302, 403)


# ─────────────────────────────────────────────────────────────────────────────
# curadoria_revisao — add/remove responsavel
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCuradoriaRevisaoResponsaveis:
    def test_post_add_responsavel_chama_api_e_redireciona(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_EXISTENTE_FAKE),
            patch("curador.views.add_responsavel_bem") as mock_add,
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-003"]),
                {"action": "add_responsavel", "user_id": "user-001", "papel": "pesquisador"},
            )
        mock_add.assert_called_once_with("abc-123", "user-001", "pesquisador")
        assert response.status_code == 302
        assert "cur-003" in response["Location"]

    def test_post_add_responsavel_api_error_redireciona_com_mensagem(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_EXISTENTE_FAKE),
            patch("curador.views.add_responsavel_bem", side_effect=ApiError("falha")),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-003"]),
                {"action": "add_responsavel", "user_id": "user-001", "papel": "pesquisador"},
            )
        assert response.status_code == 302
        assert "cur-003" in response["Location"]

    def test_post_remove_responsavel_chama_api_e_redireciona(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_EXISTENTE_FAKE),
            patch("curador.views.remove_responsavel_bem") as mock_remove,
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-003"]),
                {"action": "remove_responsavel", "responsavel_id": "resp-001"},
            )
        mock_remove.assert_called_once_with("abc-123", "resp-001")
        assert response.status_code == 302
        assert "cur-003" in response["Location"]

    def test_post_remove_responsavel_api_error_redireciona_com_mensagem(self, client, curador_user):
        from api_client.client import ApiError
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_EXISTENTE_FAKE),
            patch("curador.views.remove_responsavel_bem", side_effect=ApiError("falha")),
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-003"]),
                {"action": "remove_responsavel", "responsavel_id": "resp-001"},
            )
        assert response.status_code == 302
        assert "cur-003" in response["Location"]

    def test_post_add_responsavel_sem_bem_id_nao_chama_api(self, client, curador_user):
        client.force_login(curador_user)
        with (
            patch("curador.views.fetch_curadoria", return_value=CURADORIA_COLETA_NOVA_FAKE),
            patch("curador.views.add_responsavel_bem") as mock_add,
        ):
            response = client.post(
                reverse("curadoria-revisao", args=["cur-001"]),
                {"action": "add_responsavel", "user_id": "user-001", "papel": "pesquisador"},
            )
        mock_add.assert_not_called()
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# audit_logs — filtro por curadoria_id
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAuditLogsCuradoriaId:
    def test_get_curadoria_id_filtra_por_curadoria(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)) as mock_list:
            client.get(reverse("audit-logs") + "?curadoria_id=cur-001")
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs.get("entidade_tipo") == "App\\Models\\Curadoria"
        assert call_kwargs.get("entidade_id") == "cur-001"

    def test_get_curadoria_id_tem_prioridade_sobre_filtro(self, client, curador_user):
        client.force_login(curador_user)
        with patch("curador.views.list_auditorias", return_value=([], PAGINACAO_VAZIA)) as mock_list:
            client.get(reverse("audit-logs") + "?curadoria_id=cur-001&filtro=artigos")
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs.get("entidade_tipo") == "App\\Models\\Curadoria"
        assert call_kwargs.get("entidade_id") == "cur-001"
