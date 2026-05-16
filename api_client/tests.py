from api_client.client import (
    _normalize_number,
    _normalize_text,
    _unwrap_paginated,
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
