from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import api_client.client as client_module
from api_client.client import (
    ApiError,
    _ensure_json_text,
    _normalize_artigo,
    _normalize_auditoria,
    _normalize_autores,
    _normalize_curadoria,
    _normalize_number,
    _normalize_relations,
    _normalize_text,
    _parse_dt,
    _request,
    _unwrap_paginated,
    atualizar_curador_responsavel,
    buscar_artigo_por_doi,
    clear_api_auth_token,
    excluir_artigo_admin,
    excluir_bem_material,
    fetch_artigo_admin,
    fetch_artigos_por_bem,
    fetch_auditoria,
    fetch_bem_material,
    fetch_colaboradores_por_bem,
    fetch_curadores,
    list_artigos_admin,
    list_auditorias,
    list_curadorias,
    login_to_api,
    normalize_bem_material,
    register_to_api,
    remover_vinculo_artigo,
    request_password_reset,
    restaurar_auditoria,
    set_api_auth_token,
    submeter_artigo,
    toggle_publicado_bem_material,
    update_curadoria_avaliacao,
)


class TestNormalizeText:
    def test_none_retorna_string_vazia(self):
        assert _normalize_text(None) == ""

    def test_string_com_espacos_e_removida(self):
        assert _normalize_text("  Pedra Furada  ") == "Pedra Furada"

    def test_numero_convertido_para_string(self):
        assert _normalize_text(42) == "42"

    def test_string_vazia_retorna_vazia(self):
        assert _normalize_text("") == ""


class TestNormalizeNumber:
    def test_none_retorna_none(self):
        assert _normalize_number(None) is None

    def test_string_vazia_retorna_none(self):
        assert _normalize_number("") is None

    def test_string_numerica_convertida(self):
        assert _normalize_number("3.14") == 3.14

    def test_inteiro_convertido(self):
        assert _normalize_number(10) == 10.0

    def test_string_invalida_retorna_none(self):
        assert _normalize_number("abc") is None


class TestUnwrapPaginated:
    def test_payload_com_data(self):
        payload = {"data": [{"id": 1}], "total": 1, "current_page": 1, "last_page": 1, "per_page": 20}
        data, meta = _unwrap_paginated(payload)
        assert data == [{"id": 1}]
        assert meta["total"] == 1

    def test_payload_com_results(self):
        payload = {"results": [{"id": 2}]}
        data, _ = _unwrap_paginated(payload)
        assert data == [{"id": 2}]

    def test_payload_vazio_retorna_lista_vazia(self):
        data, meta = _unwrap_paginated({})
        assert data == []
        assert meta["page"] == 1


class TestParseDt:
    def test_string_iso_valida_retorna_datetime(self):
        result = _parse_dt("2026-01-15T10:30:00Z")
        assert result is not None
        assert hasattr(result, "year")
        assert result.year == 2026

    def test_none_retorna_none(self):
        assert _parse_dt(None) is None

    def test_string_vazia_retorna_none(self):
        assert _parse_dt("") is None

    def test_datetime_ja_parseado_retorna_igual(self):
        dt = datetime(2026, 3, 15, 12, 0, 0)
        assert _parse_dt(dt) is dt


class TestNormalizeBemMaterial:
    def _make_site(self, **overrides):
        base = {
            "id": "abc-123",
            "nome_bem": "Sítio Teste",
            "codigo_iphan": "PI-0001",
            "natureza": "arqueologico",
            "tipo": "sitio",
            "uf": "PI",
            "municipio": "Cidade",
            "latitude": -8.48,
            "longitude": -42.60,
            "publicado": True,
            "geojson": None,
            "midias": [],
            "responsavel": {},
            "nomes_populares": "",
            "artefatos": [],
            "descricao_atualizacao": "",
            "cep": "",
            "endereco": "",
            "meios_acesso": "",
            "ano_registro": 2020,
        }
        base.update(overrides)
        return base

    def test_campos_normais_retornam_dict_completo(self):
        result = normalize_bem_material(self._make_site())
        assert result["id"] == "abc-123"
        assert result["nome_bem"] == "Sítio Teste"
        assert result["codigo_iphan"] == "PI-0001"

    def test_latitude_longitude_string_convertida_para_float(self):
        result = normalize_bem_material(self._make_site(latitude="-8.48", longitude="-42.60"))
        assert result["latitude"] == -8.48
        assert result["longitude"] == -42.60

    def test_latitude_ausente_retorna_none(self):
        result = normalize_bem_material(self._make_site(latitude=None, longitude=None))
        assert result["latitude"] is None
        assert result["longitude"] is None

    def test_midias_ausentes_retornam_lista_vazia(self):
        result = normalize_bem_material(self._make_site(midias=None))
        assert result["midias"] == []

    def test_natureza_preservada_como_string(self):
        result = normalize_bem_material(self._make_site(natureza="arqueologico"))
        assert result["natureza"] == "arqueologico"


class TestNormalizeArtigo:
    def _make_entry(self, **overrides):
        base = {
            "id": "art-001",
            "titulo": "Artigo Teste",
            "doi": "10.1000/xyz",
            "autores": "Silva, João",
            "ano_publicacao": 2022,
            "periodico": "Revista",
            "idioma": "pt",
            "resumo": "Resumo.",
            "link_acesso": "https://ex.com",
            "verificado": True,
            "vinculos_count": 2,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-06-01T00:00:00Z",
            "adicionado_por": {"name": "Curador"},
            "vinculos": [],
        }
        base.update(overrides)
        return base

    def test_vinculos_count_mapeado_para_total_vinculos(self):
        result = _normalize_artigo(self._make_entry(vinculos_count=3))
        assert result["total_vinculos"] == 3

    def test_updated_at_string_convertida_para_datetime(self):
        result = _normalize_artigo(self._make_entry())
        assert result["updated_at"] is not None
        assert hasattr(result["updated_at"], "year")

    def test_vinculos_normalizados(self):
        vinculos = [
            {
                "id": "vin-001",
                "tipo_mencao": "citacao",
                "trecho_relevante": "Trecho",
                "bem_material_id": "bem-001",
                "bem_material": {"id": "bem-001", "nome_bem": "Sítio X", "codigo_iphan": "X-001", "municipio": "Cidade", "uf": "SP"},
            }
        ]
        result = _normalize_artigo(self._make_entry(vinculos=vinculos))
        assert len(result["vinculos"]) == 1
        assert result["vinculos"][0]["tipo_mencao"] == "citacao"
        assert result["vinculos"][0]["bem_material"]["nome_bem"] == "Sítio X"

    def test_campos_ausentes_retornam_defaults(self):
        result = _normalize_artigo({})
        assert result["titulo"] == ""
        assert result["total_vinculos"] == 0
        assert result["vinculos"] == []
        assert result["updated_at"] is None

    def test_adicionado_por_name_copiado_para_nome(self):
        result = _normalize_artigo(self._make_entry(adicionado_por={"name": "Fulano"}))
        assert result["adicionado_por"]["nome"] == "Fulano"

    def test_adicionado_por_ausente_retorna_dict_vazio(self):
        result = _normalize_artigo(self._make_entry(adicionado_por=None))
        assert result["adicionado_por"] == {}


class TestNormalizeAutores:
    def test_lista_de_objetos_retorna_string_separada_por_virgula(self):
        autores = [{"nome_autor": "Guidon, N.", "ordem": 0}, {"nome_autor": "Pessis, A.-M.", "ordem": 1}]
        assert _normalize_autores(autores) == "Guidon, N., Pessis, A.-M."

    def test_lista_vazia_retorna_string_vazia(self):
        assert _normalize_autores([]) == ""

    def test_string_legada_retorna_string(self):
        assert _normalize_autores("Silva, João") == "Silva, João"

    def test_none_retorna_string_vazia(self):
        assert _normalize_autores(None) == ""

    def test_objeto_sem_nome_autor_ignorado(self):
        autores = [{"nome_autor": "Guidon, N."}, {"outro_campo": "x"}]
        assert _normalize_autores(autores) == "Guidon, N."


class TestEnsureJsonText:
    def test_string_retorna_igual(self):
        assert _ensure_json_text("hello") == "hello"

    def test_none_retorna_vazio(self):
        assert _ensure_json_text(None) == ""

    def test_dict_serializado_como_json(self):
        result = _ensure_json_text({"a": 1})
        assert result == '{"a": 1}'

    def test_lista_serializada_como_json(self):
        result = _ensure_json_text([1, 2])
        assert result == "[1, 2]"


class TestNormalizeRelations:
    def test_midias_lista_direta(self):
        result = _normalize_relations({"midias": [{"id": "m1"}]})
        assert result["midias"] == [{"id": "m1"}]

    def test_midias_none_retorna_lista_vazia(self):
        result = _normalize_relations({})
        assert result["midias"] == []

    def test_midias_envolvidas_em_data(self):
        result = _normalize_relations({"midias": {"data": [{"id": "m2"}]}})
        assert result["midias"] == [{"id": "m2"}]

    def test_responsavel_envolvido_em_data_desempacotado(self):
        result = _normalize_relations({"responsavel": {"data": {"id": "u1", "name": "X"}}})
        assert result["responsavel"]["id"] == "u1"

    def test_curador_responsavel_envolvido_em_data_desempacotado(self):
        result = _normalize_relations({"curador_responsavel": {"data": {"id": "c1"}}})
        assert result["curador_responsavel"]["id"] == "c1"


class TestNormalizeAuditoria:
    def _make(self, **overrides):
        base = {
            "id": "aud-1",
            "usuario": {"id": "u1", "name": "Curador"},
            "entidade_tipo": "App\\Models\\BemMaterial",
            "entidade_id": "bem-1",
            "curadoria_id": None,
            "operacao": "Alteração",
            "meio": "Manual",
            "data_hora": "2026-05-01T10:00:00Z",
            "valor_anterior": {"nome_bem": "Antes"},
            "valor_novo": {"nome_bem": "Depois"},
            "curadoria": None,
        }
        base.update(overrides)
        return base

    def test_campos_basicos_normalizados(self):
        result = _normalize_auditoria(self._make())
        assert result["id"] == "aud-1"
        assert result["operacao"] == "Alteração"

    def test_usuario_name_copiado_para_nome(self):
        result = _normalize_auditoria(self._make(usuario={"id": "u1", "name": "Fulano"}))
        assert result["usuario"]["nome"] == "Fulano"

    def test_usuario_envolvido_em_data_desempacotado(self):
        result = _normalize_auditoria(self._make(usuario={"data": {"id": "u2", "name": "Beltrano"}}))
        assert result["usuario"]["id"] == "u2"

    def test_curadoria_envolvida_em_data_desempacotada(self):
        result = _normalize_auditoria(self._make(curadoria={"data": {"id": "c1"}}))
        assert result["curadoria"]["id"] == "c1"

    def test_data_hora_parseada_para_datetime(self):
        result = _normalize_auditoria(self._make())
        assert hasattr(result["data_hora"], "year")

    def test_valor_anterior_none_retorna_dict_vazio(self):
        result = _normalize_auditoria(self._make(valor_anterior=None))
        assert result["valor_anterior"] == {}


class TestNormalizeCuradoria:
    def _make(self, **overrides):
        base = {
            "id": "cur-1",
            "entidade_tipo": "coleta",
            "entidade_id": "col-1",
            "status": "pendente",
            "usuario": {"id": "u1", "name": "Fulano"},
            "curador": {"id": "c1", "name": "Curador X"},
            "coleta": {"id": "col-1"},
            "bem_material": {},
            "submissao_artigo": {},
        }
        base.update(overrides)
        return base

    def test_campos_basicos_normalizados(self):
        result = _normalize_curadoria(self._make())
        assert result["id"] == "cur-1"
        assert result["status"] == "pendente"

    def test_usuario_name_copiado_para_nome(self):
        result = _normalize_curadoria(self._make())
        assert result["usuario"]["nome"] == "Fulano"

    def test_curador_name_copiado_para_nome(self):
        result = _normalize_curadoria(self._make())
        assert result["curador"]["nome"] == "Curador X"

    def test_curador_envolvido_em_data_desempacotado(self):
        result = _normalize_curadoria(self._make(curador={"data": {"id": "c2", "name": "Outro"}}))
        assert result["curador"]["id"] == "c2"


class TestHeaders:
    def setup_method(self):
        clear_api_auth_token()

    def test_sem_token_nao_inclui_authorization(self):
        headers = client_module._headers()
        assert "Authorization" not in headers
        assert headers["Accept"] == "application/json"

    def test_com_token_inclui_bearer(self):
        set_api_auth_token("meu-token-123")
        headers = client_module._headers()
        assert headers["Authorization"] == "Bearer meu-token-123"

    def test_set_none_limpa_token(self):
        set_api_auth_token("tok")
        set_api_auth_token(None)
        assert "Authorization" not in client_module._headers()

    def test_sem_token_ignora_token_da_sessao(self):
        set_api_auth_token("tok")
        assert "Authorization" not in client_module._headers(sem_token=True)

    def test_chave_do_site_vai_no_cabecalho(self):
        # P23: com a chave, a API dá ao site um limite próprio.
        with patch.object(client_module, "API_CLIENT_KEY", "segredo"):
            assert client_module._headers(sem_token=True)["X-Client-Key"] == "segredo"
        with patch.object(client_module, "API_CLIENT_KEY", ""):
            assert "X-Client-Key" not in client_module._headers()


class TestCacheDeBensSemToken:
    """O cache de bens é compartilhado entre usuários: não pode guardar dados de curador."""

    def setup_method(self):
        clear_api_auth_token()
        client_module.invalidate_bens_cache()

    def teardown_method(self):
        clear_api_auth_token()
        client_module.invalidate_bens_cache()

    def test_cache_busca_bens_como_visitante_mesmo_com_curador_logado(self):
        set_api_auth_token("token-de-curador")
        resposta = MagicMock(status_code=200, content=b"x", text="")
        resposta.json.return_value = {"data": [], "last_page": 1}

        with patch("requests.request", return_value=resposta) as chamada:
            client_module.fetch_all_bens_materiais()

        assert "Authorization" not in chamada.call_args.kwargs["headers"]


class TestNomesPopulares:
    def test_lista_vira_texto_separado_por_virgula(self):
        site = client_module.normalize_bem_material({"id": "1", "nomes_populares": ["Pedra Furada", "Toca"]})
        assert site["nomes_populares"] == "Pedra Furada, Toca"

    def test_lista_vazia_vira_texto_vazio(self):
        site = client_module.normalize_bem_material({"id": "1", "nomes_populares": []})
        assert site["nomes_populares"] == ""

    def test_texto_continua_texto(self):
        site = client_module.normalize_bem_material({"id": "1", "nomes_populares": "Toca"})
        assert site["nomes_populares"] == "Toca"


class TestRequest:
    def _mock_response(self, status=200, json_data=None, text="", content=b"x"):
        resp = MagicMock()
        resp.status_code = status
        resp.content = content
        resp.text = text
        resp.json.return_value = json_data if json_data is not None else {}
        return resp

    def test_sucesso_retorna_json(self):
        with patch("requests.request", return_value=self._mock_response(json_data={"ok": True})):
            result = _request("GET", "/teste")
        assert result == {"ok": True}

    def test_resposta_vazia_retorna_dict_vazio(self):
        resp = self._mock_response(content=b"")
        with patch("requests.request", return_value=resp):
            result = _request("DELETE", "/teste")
        assert result == {}

    def test_erro_400_levanta_api_error(self):
        resp = self._mock_response(status=400, text="Bad Request", content=b"Bad Request")
        with patch("requests.request", return_value=resp):
            with pytest.raises(ApiError) as exc:
                _request("POST", "/teste")
        assert exc.value.status_code == 400

    def test_erro_422_extrai_message_do_json(self):
        resp = self._mock_response(status=422, text="err", content=b"err", json_data={"message": "Campo inválido"})
        with patch("requests.request", return_value=resp):
            with pytest.raises(ApiError) as exc:
                _request("POST", "/teste")
        assert "Campo inválido" in exc.value.message

    def test_erro_500_levanta_api_error(self):
        resp = self._mock_response(status=500, text="Server Error", content=b"err")
        with patch("requests.request", return_value=resp):
            with pytest.raises(ApiError) as exc:
                _request("GET", "/teste")
        assert exc.value.status_code == 500

    def test_json_invalido_levanta_api_error(self):
        resp = self._mock_response(content=b"not-json")
        resp.json.side_effect = ValueError("no JSON")
        with patch("requests.request", return_value=resp):
            with pytest.raises(ApiError):
                _request("GET", "/teste")


class TestLoginToApi:
    def test_sucesso_retorna_token_e_usuario(self):
        payload = {"token": "abc123", "user": {"id": "u1", "name": "João"}}
        with patch("api_client.client._request", return_value=payload):
            token, user = login_to_api("joao@test.com", "senha")
        assert token == "abc123"
        assert user["id"] == "u1"

    def test_token_ausente_levanta_api_error(self):
        with patch("api_client.client._request", return_value={"user": {}}):
            with pytest.raises(ApiError):
                login_to_api("joao@test.com", "senha")


class TestRegisterToApi:
    def test_sucesso_retorna_token_e_usuario(self):
        payload = {"token": "tok-reg", "user": {"id": "u2"}}
        with patch("api_client.client._request", return_value=payload) as mock_request:
            token, user = register_to_api("João", "j@test.com", "senha", "senha", "estudante")
        assert token == "tok-reg"
        # P22: a API guarda a data do aceite dos termos.
        assert mock_request.call_args.kwargs["json_body"]["termos_aceitos"] is True

    def test_token_ausente_levanta_api_error(self):
        with patch("api_client.client._request", return_value={}):
            with pytest.raises(ApiError):
                register_to_api("João", "j@test.com", "senha", "senha", "estudante")


class TestRequestPasswordReset:
    def test_retorna_mensagem_da_api(self):
        with patch("api_client.client._request", return_value={"message": "Email enviado"}):
            result = request_password_reset("j@test.com")
        assert result == "Email enviado"


class TestBuscarArtigoPorDoi:
    def test_retorna_artigo_quando_encontrado(self):
        artigo = {"id": "art-1", "titulo": "Teste"}
        with patch("api_client.client._request", return_value={"artigo": artigo}):
            result = buscar_artigo_por_doi("10.1000/test")
        assert result["id"] == "art-1"

    def test_retorna_none_em_api_error(self):
        with patch("api_client.client._request", side_effect=ApiError("Not found", 404)):
            result = buscar_artigo_por_doi("10.1000/inexistente")
        assert result is None

    def test_retorna_none_quando_artigo_ausente_no_payload(self):
        with patch("api_client.client._request", return_value={}):
            result = buscar_artigo_por_doi("10.1000/test")
        assert result is None


class TestWrappersHTTP:
    """Testes mínimos dos wrappers HTTP — verificam parsing de resposta e tratamento de erro."""

    def test_fetch_artigos_por_bem_retorna_lista(self):
        with patch("api_client.client._request", return_value={"artigos": [{"id": "a1"}]}):
            result = fetch_artigos_por_bem("bem-1")
        assert result == [{"id": "a1"}]

    def test_fetch_artigos_por_bem_retorna_vazio_sem_chave(self):
        with patch("api_client.client._request", return_value={}):
            assert fetch_artigos_por_bem("bem-1") == []

    def test_fetch_colaboradores_retorna_lista(self):
        with patch("api_client.client._request", return_value={"colaboradores": [{"id": "u1"}]}):
            result = fetch_colaboradores_por_bem("bem-1")
        assert result[0]["id"] == "u1"

    def test_fetch_curadores_retorna_lista(self):
        with patch("api_client.client._request", return_value={"data": [{"id": "c1"}]}):
            result = fetch_curadores()
        assert result[0]["id"] == "c1"

    def test_list_auditorias_retorna_normalizado(self):
        payload = {"data": [{"id": "aud-1", "operacao": "Inserção"}], "total": 1, "current_page": 1, "last_page": 1, "per_page": 20}
        with patch("api_client.client._request", return_value=payload):
            items, meta = list_auditorias()
        assert items[0]["id"] == "aud-1"

    def test_fetch_auditoria_levanta_erro_para_resposta_invalida(self):
        with patch("api_client.client._request", return_value="string-invalida"):
            with pytest.raises(ApiError):
                fetch_auditoria("aud-1")

    def test_list_curadorias_retorna_normalizado(self):
        payload = {"data": [{"id": "cur-1", "status": "pendente"}], "total": 1, "current_page": 1, "last_page": 1, "per_page": 20}
        with patch("api_client.client._request", return_value=payload):
            items, _ = list_curadorias()
        assert items[0]["id"] == "cur-1"

    def test_update_curadoria_avaliacao_levanta_erro_para_resposta_invalida(self):
        with patch("api_client.client._request", return_value="invalido"):
            with pytest.raises(ApiError):
                update_curadoria_avaliacao("cur-1", {})

    def test_submeter_artigo_retorna_payload(self):
        with patch("api_client.client._request", return_value={"id": "sub-1"}):
            result = submeter_artigo({"doi": "10.x/y"})
        assert result["id"] == "sub-1"

    def test_remover_vinculo_artigo_nao_levanta_erro(self):
        with patch("api_client.client._request", return_value={}):
            remover_vinculo_artigo("vin-1")

    def test_toggle_publicado_levanta_erro_para_resposta_invalida(self):
        with patch("api_client.client._request", return_value="invalido"):
            with pytest.raises(ApiError):
                toggle_publicado_bem_material("bem-1", True)

    def test_atualizar_curador_responsavel_levanta_erro_para_resposta_invalida(self):
        with patch("api_client.client._request", return_value="invalido"):
            with pytest.raises(ApiError):
                atualizar_curador_responsavel("bem-1", "c1")

    def test_excluir_bem_material_nao_levanta_erro(self):
        with patch("api_client.client._request", return_value={}):
            excluir_bem_material("bem-1")

    def test_restaurar_auditoria_retorna_payload(self):
        with patch("api_client.client._request", return_value={"message": "ok"}):
            result = restaurar_auditoria("aud-1")
        assert result["message"] == "ok"

    def test_list_artigos_admin_retorna_normalizado(self):
        payload = {"data": [{"id": "art-1", "titulo": "X", "vinculos_count": 0}]}
        with patch("api_client.client._request", return_value=payload):
            result = list_artigos_admin()
        assert result[0]["id"] == "art-1"

    def test_fetch_artigo_admin_levanta_erro_para_resposta_invalida(self):
        with patch("api_client.client._request", return_value="invalido"):
            with pytest.raises(ApiError):
                fetch_artigo_admin("art-1")

    def test_excluir_artigo_admin_nao_levanta_erro(self):
        with patch("api_client.client._request", return_value={}):
            excluir_artigo_admin("art-1")

    def test_fetch_bem_material_retorna_normalizado(self):
        payload = {"data": {"id": "bem-1", "nome_bem": "Pedra Furada", "publicado": True}}
        with patch("api_client.client._request", return_value=payload):
            result = fetch_bem_material("bem-1")
        assert result["id"] == "bem-1"
        assert result["nome_bem"] == "Pedra Furada"

    def test_fetch_bem_material_levanta_erro_para_resposta_invalida(self):
        with patch("api_client.client._request", return_value="invalido"):
            with pytest.raises(ApiError):
                fetch_bem_material("bem-1")

    def test_fetch_auditoria_retorna_normalizado(self):
        payload = {"data": {"id": "aud-1", "operacao": "Inserção"}}
        with patch("api_client.client._request", return_value=payload):
            result = fetch_auditoria("aud-1")
        assert result["id"] == "aud-1"

    def test_update_curadoria_avaliacao_retorna_normalizado(self):
        payload = {"data": {"id": "cur-1", "status": "aprovado"}}
        with patch("api_client.client._request", return_value=payload):
            result = update_curadoria_avaliacao("cur-1", {"status": "aprovado"})
        assert result["id"] == "cur-1"

    def test_toggle_publicado_retorna_bem_normalizado(self):
        payload = {"data": {"id": "bem-1", "nome_bem": "X", "publicado": True}}
        with patch("api_client.client._request", return_value=payload):
            result = toggle_publicado_bem_material("bem-1", True)
        assert result["id"] == "bem-1"

    def test_atualizar_curador_responsavel_retorna_bem_normalizado(self):
        payload = {"data": {"id": "bem-1", "nome_bem": "X"}}
        with patch("api_client.client._request", return_value=payload):
            result = atualizar_curador_responsavel("bem-1", "c1")
        assert result["id"] == "bem-1"

    def test_fetch_artigo_admin_retorna_normalizado(self):
        payload = {"data": {"id": "art-1", "titulo": "Artigo X", "vinculos_count": 2}}
        with patch("api_client.client._request", return_value=payload):
            result = fetch_artigo_admin("art-1")
        assert result["id"] == "art-1"
        assert result["total_vinculos"] == 2

    def test_list_auditorias_com_filtros(self):
        payload = {"data": [], "total": 0, "current_page": 1, "last_page": 1, "per_page": 20}
        with patch("api_client.client._request", return_value=payload) as mock_req:
            list_auditorias(entidade_tipo="BemMaterial", entidade_id="bem-1", usuario_id="u1")
        _, kwargs = mock_req.call_args
        assert kwargs["params"]["entidade_tipo"] == "BemMaterial"
        assert kwargs["params"]["entidade_id"] == "bem-1"
        assert kwargs["params"]["usuario_id"] == "u1"

    def test_list_curadorias_com_status(self):
        payload = {"data": [], "total": 0, "current_page": 1, "last_page": 1, "per_page": 20}
        with patch("api_client.client._request", return_value=payload) as mock_req:
            list_curadorias(status="aprovado")
        _, kwargs = mock_req.call_args
        assert kwargs["params"]["status"] == "aprovado"


class TestFetchAllBensMateriais:
    def _page(self, items, current=1, last=1):
        return {
            "data": items,
            "total": len(items),
            "current_page": current,
            "last_page": last,
            "per_page": 20,
        }

    def _make_bem(self, bem_id):
        return {"id": bem_id, "nome_bem": f"Sítio {bem_id}", "publicado": True}

    def test_pagina_unica_retorna_todos(self):
        from api_client.client import fetch_all_bens_materiais, invalidate_bens_cache
        invalidate_bens_cache()
        payload = self._page([self._make_bem("b1"), self._make_bem("b2")])
        with patch("api_client.client._request", return_value=payload):
            result = fetch_all_bens_materiais()
        assert len(result) == 2
        assert result[0]["id"] == "b1"

    def test_multiplas_paginas_acumula_todos(self):
        from api_client.client import fetch_all_bens_materiais, invalidate_bens_cache
        invalidate_bens_cache()
        pagina1 = self._page([self._make_bem("b1")], current=1, last=2)
        pagina2 = self._page([self._make_bem("b2")], current=2, last=2)
        with patch("api_client.client._request", side_effect=[pagina1, pagina2]):
            result = fetch_all_bens_materiais()
        assert len(result) == 2

    def test_cache_evita_segunda_chamada(self):
        from api_client.client import fetch_all_bens_materiais, invalidate_bens_cache
        invalidate_bens_cache()
        payload = self._page([self._make_bem("b1")])
        with patch("api_client.client._request", return_value=payload) as mock_req:
            fetch_all_bens_materiais()
            fetch_all_bens_materiais()
        assert mock_req.call_count == 1

    def test_invalidate_forca_nova_chamada(self):
        from api_client.client import fetch_all_bens_materiais, invalidate_bens_cache
        invalidate_bens_cache()
        payload = self._page([self._make_bem("b1")])
        with patch("api_client.client._request", return_value=payload) as mock_req:
            fetch_all_bens_materiais()
            invalidate_bens_cache()
            fetch_all_bens_materiais()
        assert mock_req.call_count == 2


class TestFetchAllCuradorias:
    def _page(self, items, current=1, last=1):
        return {
            "data": items,
            "total": len(items),
            "current_page": current,
            "last_page": last,
            "per_page": 20,
        }

    def test_pagina_unica_retorna_tuple(self):
        from api_client.client import fetch_all_curadorias
        payload = self._page([{"id": "c1", "status": "pendente"}])
        with patch("api_client.client._request", return_value=payload):
            result = fetch_all_curadorias()
        assert isinstance(result, tuple)
        assert result[0]["id"] == "c1"

    def test_multiplas_paginas_acumula(self):
        from api_client.client import fetch_all_curadorias
        p1 = self._page([{"id": "c1"}], current=1, last=2)
        p2 = self._page([{"id": "c2"}], current=2, last=2)
        with patch("api_client.client._request", side_effect=[p1, p2]):
            result = fetch_all_curadorias()
        assert len(result) == 2

    def test_fetch_curadoria_encontra_por_id(self):
        from api_client.client import fetch_curadoria
        payload = {"data": {"id": "cur-alvo", "status": "aprovado"}}
        with patch("api_client.client._request", return_value=payload):
            result = fetch_curadoria("cur-alvo")
        assert result["id"] == "cur-alvo"

    def test_fetch_curadoria_levanta_erro_quando_nao_encontrada(self):
        from api_client.client import fetch_curadoria
        with patch("api_client.client._request", return_value="not-found"):
            with pytest.raises(ApiError):
                fetch_curadoria("inexistente")
