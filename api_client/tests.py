from datetime import datetime

from api_client.client import (
    _normalize_number,
    _normalize_text,
    _parse_dt,
    _unwrap_paginated,
    normalize_bem_material,
    _normalize_artigo,
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
