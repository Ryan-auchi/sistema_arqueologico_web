from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextvars import ContextVar
from typing import Any
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8001/api/v1").rstrip("/")
API_AUTH_BASE_URL = os.environ.get(
    "API_AUTH_BASE_URL",
    API_BASE_URL.rsplit("/v1", 1)[0] if API_BASE_URL.endswith("/api/v1") else API_BASE_URL,
).rstrip("/")
API_TIMEOUT = float(os.environ.get("API_TIMEOUT", "15"))
_API_AUTH_TOKEN_CONTEXT: ContextVar[str] = ContextVar("api_auth_token", default="")


def set_api_auth_token(token: str | None) -> None:
    _API_AUTH_TOKEN_CONTEXT.set((token or "").strip())


def clear_api_auth_token() -> None:
    _API_AUTH_TOKEN_CONTEXT.set("")


def _current_api_auth_token() -> str:
    token = _API_AUTH_TOKEN_CONTEXT.get().strip()
    return token


def _headers(sem_token: bool = False) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = "" if sem_token else _current_api_auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    base_url: str | None = None,
    sem_token: bool = False,
) -> dict[str, Any]:
    request_base_url = (base_url or API_BASE_URL).rstrip("/")
    url = urljoin(f"{request_base_url}/", path.lstrip("/"))
    response = requests.request(
        method=method,
        url=url,
        params=params,
        json=json_body,
        headers=_headers(sem_token),
        timeout=API_TIMEOUT,
    )

    if response.status_code >= 400:
        detail = response.text.strip()
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = _normalize_text(payload.get("message")) or detail
        except ValueError:
            pass
        raise ApiError(detail or f"API request failed ({response.status_code}) for {url}", response.status_code)

    if not response.content:
        return {}

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError(f"API returned invalid JSON for {url}") from exc


def login_to_api(email: str, password: str) -> tuple[str, dict[str, Any]]:
    payload = _request(
        "POST",
        "/auth/login",
        json_body={"email": email, "password": password},
        base_url=API_AUTH_BASE_URL,
    )

    token = _normalize_text(payload.get("token"))
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}

    if not token:
        raise ApiError("API authentication did not return a token.")

    return token, user


def register_to_api(
    name: str,
    email: str,
    password: str,
    password_confirmation: str,
    classificacao: str,
) -> tuple[str, dict[str, Any]]:
    payload = _request(
        "POST",
        "/auth/register",
        json_body={
            "name": name,
            "email": email,
            "password": password,
            "password_confirmation": password_confirmation,
            "classificacao": classificacao,
        },
        base_url=API_AUTH_BASE_URL,
    )

    token = _normalize_text(payload.get("token"))
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}

    if not token:
        raise ApiError("API registration did not return a token.")

    return token, user


def delete_own_account() -> None:
    _request("DELETE", "/auth/conta", base_url=API_AUTH_BASE_URL)


def logout_from_api() -> None:
    _request("POST", "/auth/logout", base_url=API_AUTH_BASE_URL)


def request_password_reset(email: str) -> str:
    payload = _request(
        "POST",
        "/auth/password-reset",
        json_body={"email": email},
        base_url=API_AUTH_BASE_URL,
    )
    return _normalize_text(payload.get("message"))


def confirm_password_reset(email: str, token: str, password: str, password_confirmation: str) -> str:
    payload = _request(
        "POST",
        "/auth/password-reset/confirm",
        json_body={
            "email": email,
            "token": token,
            "password": password,
            "password_confirmation": password_confirmation,
        },
        base_url=API_AUTH_BASE_URL,
    )
    return _normalize_text(payload.get("message"))


def _unwrap_paginated(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(payload.get("data"), list):
        data = payload["data"]
    elif isinstance(payload.get("results"), list):
        data = payload["results"]
    else:
        data = []

    meta = {
        "total": payload.get("total") or payload.get("meta", {}).get("total", len(data)),
        "page": payload.get("current_page") or payload.get("meta", {}).get("page", 1),
        "pages": payload.get("last_page") or payload.get("meta", {}).get("pages", 1),
        "per_page": payload.get("per_page") or payload.get("meta", {}).get("per_page", len(data) or 1),
    }
    return data, meta


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_lista_texto(value: Any) -> str:
    """A API devolve listas (ex.: nomes populares); a interface mostra texto separado por vírgula.

    Aceita ["A", "B"] (resource) e [{"nome": "A"}] (modelo, como na revisão de curadoria).
    """
    if isinstance(value, list):
        textos = (_normalize_text(item.get("nome") if isinstance(item, dict) else item) for item in value)
        return ", ".join(texto for texto in textos if texto)
    return _normalize_text(value)


def _normalize_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_datetime(value: Any) -> str:
    return _normalize_text(value)


def _parse_dt(value: Any):
    """Converte string ISO 8601 para datetime; retorna None se inválido."""
    if not value:
        return None
    if hasattr(value, "year"):
        return value
    from django.utils.dateparse import parse_datetime

    return parse_datetime(str(value).strip()) or None


def _ensure_json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def _normalize_relations(site: dict[str, Any]) -> dict[str, Any]:
    midias = site.get("midias") or []
    if isinstance(midias, dict):
        midias = midias.get("data", []) if isinstance(midias.get("data"), list) else []

    responsavel = site.get("responsavel") or {}
    if isinstance(responsavel, dict) and "data" in responsavel and isinstance(responsavel["data"], dict):
        responsavel = responsavel["data"]

    curador_responsavel = site.get("curador_responsavel") or {}
    if isinstance(curador_responsavel, dict) and "data" in curador_responsavel and isinstance(curador_responsavel["data"], dict):
        curador_responsavel = curador_responsavel["data"]

    responsaveis_raw = site.get("responsaveis") or []
    if isinstance(responsaveis_raw, dict):
        responsaveis_raw = responsaveis_raw.get("data") or []
    responsaveis: list[dict[str, Any]] = []
    for r in (responsaveis_raw if isinstance(responsaveis_raw, list) else []):
        if not isinstance(r, dict):
            continue
        u = r.get("user") or r.get("usuario") or {}
        if isinstance(u, dict) and "data" in u:
            u = u.get("data") or {}
        responsaveis.append({
            "id": r.get("id") or "",
            "user_id": r.get("user_id") or "",
            "papel": r.get("papel") or "",
            "nome": u.get("name") or u.get("nome") or "",
            "email": u.get("email") or "",
        })

    return {
        "midias": midias if isinstance(midias, list) else [],
        "responsavel": responsavel if isinstance(responsavel, dict) else {},
        "curador_responsavel": curador_responsavel if isinstance(curador_responsavel, dict) else {},
        "responsaveis": responsaveis,
    }


def _normalize_artefatos(site: dict[str, Any]) -> list[str]:
    pivot = site.get("artefato_tipos")
    if isinstance(pivot, list) and pivot:
        nomes = []
        for entry in pivot:
            if not isinstance(entry, dict):
                continue
            # Formato flat: {"id": ..., "nome": ...}
            nome = _normalize_text(entry.get("nome"))
            if not nome:
                # Formato do modelo (revisão de curadoria): {"descricao_nova": ..., "artefato_tipo": {"nome": ...}}.
                # Em "Outros", a descrição diz o que foi achado.
                nome = _normalize_text(entry.get("descricao_nova") or (entry.get("artefato_tipo") or {}).get("nome"))
            if nome:
                nomes.append(nome)
        return nomes
    # Formato legado: artefatos como lista de strings
    legacy = site.get("artefatos")
    if isinstance(legacy, list):
        return [str(a) for a in legacy if a]
    return []


def normalize_bem_material(site: dict[str, Any]) -> dict[str, Any]:
    relations = _normalize_relations(site)
    geojson = site.get("geojson")
    geometry = geojson
    if isinstance(geojson, str) and geojson:
        try:
            geometry = json.loads(geojson)
        except ValueError:
            geometry = None

    natureza = _normalize_text(site.get("natureza"))
    tipo = _normalize_text(site.get("tipo"))
    published = bool(site.get("publicado"))

    return {
        "id": _normalize_text(site.get("id")),
        "coleta_id": _normalize_text(site.get("coleta_id")),
        "codigo_iphan": _normalize_text(site.get("codigo_iphan")),
        "nome_bem": _normalize_text(site.get("nome_bem")),
        "nomes_populares": _normalize_lista_texto(site.get("nomes_populares")),
        "natureza": natureza,
        "tipo": tipo,
        "meios_acesso": _normalize_text(site.get("meios_acesso")),
        "artefatos": _normalize_artefatos(site),
        "publicado": published,
        "published": published,
        "published_label": "Publicado" if published else "Nao publicado",
        "uf": _normalize_text(site.get("uf")).upper(),
        "municipio": _normalize_text(site.get("municipio")),
        "cep": _normalize_text((site.get("localizacao") or {}).get("cep") or site.get("cep")),
        "endereco": _normalize_text((site.get("localizacao") or {}).get("logradouro") or site.get("endereco")),
        "latitude": _normalize_number((site.get("localizacao") or {}).get("lat") or site.get("latitude")),
        "longitude": _normalize_number((site.get("localizacao") or {}).get("lng") or site.get("longitude")),
        "geojson": geojson,
        "geometry": geometry,
        "geometry_type": geometry.get("type", "") if isinstance(geometry, dict) else "",
        "ano_registro": site.get("ano_registro"),
        "descricao_atualizacao": _normalize_text(site.get("descricao_atualizacao")),
        "criado_em": _normalize_datetime(site.get("criado_em") or site.get("created_at")),
        "atualizado_em": _normalize_datetime(site.get("atualizado_em") or site.get("updated_at")),
        "deletado_em": _normalize_datetime(site.get("deletado_em") or site.get("deleted_at")),
        "midias": relations["midias"],
        "responsavel": relations["responsavel"],
        "curador_responsavel": relations["curador_responsavel"],
        "responsaveis": relations["responsaveis"],
    }


def _normalize_auditoria(entry: dict[str, Any]) -> dict[str, Any]:
    usuario = entry.get("usuario") or {}
    if isinstance(usuario, dict) and "data" in usuario and isinstance(usuario["data"], dict):
        usuario = usuario["data"]
    if isinstance(usuario, dict) and usuario.get("name") and not usuario.get("nome"):
        usuario["nome"] = usuario.get("name")

    curadoria = entry.get("curadoria") or {}
    if isinstance(curadoria, dict) and "data" in curadoria and isinstance(curadoria["data"], dict):
        curadoria = curadoria["data"]

    data_hora = entry.get("data_hora") or entry.get("created_at")
    if isinstance(data_hora, str) and data_hora:
        try:
            from django.utils.dateparse import parse_datetime

            data_hora = parse_datetime(data_hora) or data_hora
        except Exception:
            pass

    return {
        "id": _normalize_text(entry.get("id")),
        "usuario": usuario if isinstance(usuario, dict) else {},
        "entidade_tipo": _normalize_text(entry.get("entidade_tipo")),
        "entidade_id": _normalize_text(entry.get("entidade_id")),
        "curadoria_id": _normalize_text(entry.get("curadoria_id")),
        "operacao": _normalize_text(entry.get("operacao")),
        "meio": _normalize_text(entry.get("meio")),
        "data_hora": data_hora if data_hora else _normalize_datetime(entry.get("data_hora") or entry.get("created_at")),
        "valor_anterior": entry.get("valor_anterior") or {},
        "valor_novo": entry.get("valor_novo") or {},
        "curadoria": curadoria if isinstance(curadoria, dict) else {},
    }


def _normalize_curadoria(entry: dict[str, Any]) -> dict[str, Any]:
    usuario = entry.get("usuario") or {}
    if isinstance(usuario, dict) and "data" in usuario and isinstance(usuario["data"], dict):
        usuario = usuario["data"]
    if isinstance(usuario, dict) and usuario.get("name") and not usuario.get("nome"):
        usuario["nome"] = usuario.get("name")

    curador = entry.get("curador") or {}
    if isinstance(curador, dict) and "data" in curador and isinstance(curador["data"], dict):
        curador = curador["data"]
    if isinstance(curador, dict) and curador.get("name") and not curador.get("nome"):
        curador["nome"] = curador.get("name")

    coleta = entry.get("coleta") or {}
    bem_material = entry.get("bem_material") or {}
    submissao_artigo = entry.get("submissao_artigo") or {}

    return {
        "id": _normalize_text(entry.get("id")),
        "entidade_tipo": _normalize_text(entry.get("entidade_tipo")),
        "entidade_id": _normalize_text(entry.get("entidade_id")),
        "coleta_id": _normalize_text(entry.get("coleta_id")),
        "bem_material_id": _normalize_text(entry.get("bem_material_id")),
        "usuario_id": _normalize_text(entry.get("usuario_id")),
        "status": _normalize_text(entry.get("status")),
        "acao_resultante": _normalize_text(entry.get("acao_resultante")),
        "data_avaliacao": _normalize_datetime(entry.get("data_avaliacao") or entry.get("created_at")),
        "observacao": _normalize_text(entry.get("observacao")),
        "criado_em": _normalize_datetime(entry.get("created_at")),
        "atualizado_em": _normalize_datetime(entry.get("updated_at")),
        "coleta": coleta if isinstance(coleta, dict) else {},
        "submissao_artigo": submissao_artigo if isinstance(submissao_artigo, dict) else {},
        "bem_material": bem_material if isinstance(bem_material, dict) else {},
        "usuario": usuario if isinstance(usuario, dict) else {},
        "curador": curador if isinstance(curador, dict) else {},
    }


# ---------------------------------------------------------------------------
# Thread-safe TTL cache for bens materiais
# ---------------------------------------------------------------------------
_BENS_CACHE_TTL = 300  # seconds — 5 min é suficiente para navegação consecutiva
_bens_cache_lock = threading.Lock()
_bens_cache_data: tuple[dict[str, Any], ...] | None = None
_bens_cache_ts: float = 0.0


def invalidate_bens_cache() -> None:
    """Force the next call to fetch_all_bens_materiais() to hit the API."""
    global _bens_cache_data, _bens_cache_ts
    with _bens_cache_lock:
        _bens_cache_data = None
        _bens_cache_ts = 0.0


def fetch_all_bens_materiais() -> tuple[dict[str, Any], ...]:
    global _bens_cache_data, _bens_cache_ts
    with _bens_cache_lock:
        if _bens_cache_data is not None and (time.monotonic() - _bens_cache_ts) < _BENS_CACHE_TTL:
            return _bens_cache_data

    page = 1
    results: list[dict[str, Any]] = []

    while True:
        # O cache é compartilhado entre todos os usuários: busca sempre como visitante,
        # para não guardar dados que só um curador pode ver (ex.: e-mails).
        payload = _request("GET", "/mobile/bens-materiais", params={"page": page, "publicado": "all"}, sem_token=True)
        items, meta = _unwrap_paginated(payload)

        results.extend(normalize_bem_material(item) for item in items)

        if page >= int(meta["pages"] or 1):
            break

        page += 1

    fresh = tuple(results)
    with _bens_cache_lock:
        _bens_cache_data = fresh
        _bens_cache_ts = time.monotonic()
    return fresh


def fetch_bem_material(bem_id: str) -> dict[str, Any]:
    payload = _request("GET", f"/mobile/bens-materiais/{bem_id}")
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise ApiError("API response for bem material detail was not an object")
    return normalize_bem_material(data)


def list_auditorias(
    *, entidade_tipo: str | None = None, entidade_id: str | None = None, usuario_id: str | None = None, page: int = 1
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params: dict[str, Any] = {"page": page}
    if entidade_tipo:
        params["entidade_tipo"] = entidade_tipo
    if entidade_id:
        params["entidade_id"] = entidade_id
    if usuario_id:
        params["usuario_id"] = usuario_id

    payload = _request("GET", "/admin/auditorias", params=params)
    items, meta = _unwrap_paginated(payload)
    return [_normalize_auditoria(item) for item in items if isinstance(item, dict)], meta


def fetch_auditoria(audit_id: str) -> dict[str, Any]:
    response = _request("GET", f"/admin/auditorias/{audit_id}")
    data = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else response
    if not isinstance(data, dict):
        raise ApiError("API response for auditoria detail was not an object")
    return _normalize_auditoria(data)


def list_curadorias(*, status: str | None = None, page: int = 1) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params: dict[str, Any] = {"page": page}
    if status:
        params["status"] = status

    payload = _request("GET", "/admin/curadorias", params=params)
    items, meta = _unwrap_paginated(payload)
    return [_normalize_curadoria(item) for item in items if isinstance(item, dict)], meta


def fetch_all_curadorias(*, status: str | None = None) -> tuple[dict[str, Any], ...]:
    page = 1
    results: list[dict[str, Any]] = []

    while True:
        items, meta = list_curadorias(status=status, page=page)
        results.extend(items)

        if page >= int(meta["pages"] or 1):
            break

        page += 1

    return tuple(results)


def fetch_curadoria(curadoria_id: str) -> dict[str, Any]:
    data = _request("GET", f"/admin/curadorias/{curadoria_id}")
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]
    if not isinstance(data, dict):
        raise ApiError("Curadoria não encontrada", 404)
    return data


def fetch_curadorias_por_bem(bem_id: str) -> list[dict[str, Any]]:
    page = 1
    results: list[dict[str, Any]] = []
    while True:
        payload = _request("GET", f"/admin/bens-materiais/{bem_id}/curadorias", params={"page": page})
        items, meta = _unwrap_paginated(payload)
        results.extend(_normalize_curadoria(item) for item in items if isinstance(item, dict))
        if page >= int(meta["pages"] or 1):
            break
        page += 1
    return results


def update_curadoria_avaliacao(curadoria_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = _request("PATCH", f"/admin/curadorias/{curadoria_id}/avaliar", json_body=payload)
    data = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else response
    if not isinstance(data, dict):
        raise ApiError("API response for curadoria update was not an object")
    return _normalize_curadoria(data)


def fetch_auditorias_for_bem(bem_id: str, *, entidade_tipo: str) -> list[dict[str, Any]]:
    page = 1
    entries: list[dict[str, Any]] = []

    while True:
        items, meta = list_auditorias(entidade_tipo=entidade_tipo, entidade_id=bem_id, page=page)
        entries.extend(items)

        if page >= int(meta["pages"] or 1):
            break

        page += 1

    return entries


def fetch_artigos_por_bem(bem_id: str) -> list[dict[str, Any]]:
    payload = _request("GET", f"/mobile/bens-materiais/{bem_id}/artigos")
    return payload.get("artigos", []) if isinstance(payload, dict) else []


def buscar_artigo_por_doi(doi: str) -> dict[str, Any] | None:
    try:
        payload = _request("GET", "/mobile/artigos-cientificos/buscar-doi", params={"doi": doi})
        artigo = payload.get("artigo") if isinstance(payload, dict) else None
        return artigo if isinstance(artigo, dict) else None
    except ApiError:
        return None


def submeter_artigo(payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", "/mobile/submissoes-artigos", json_body=payload)


def remover_vinculo_artigo(vinculo_id: str) -> None:
    _request("DELETE", f"/admin/artigos-bem-material/{vinculo_id}")


def fetch_colaboradores_por_bem(bem_id: str) -> list[dict[str, Any]]:
    """Retorna colaboradores do bem material. Levanta ApiError em caso de falha."""
    payload = _request("GET", f"/mobile/bens-materiais/{bem_id}/colaboradores")
    return payload.get("colaboradores", []) if isinstance(payload, dict) else []


def toggle_publicado_bem_material(bem_id: str, publicado: bool) -> dict[str, Any]:
    response = _request("PATCH", f"/admin/bens-materiais/{bem_id}/publicar", json_body={"publicado": publicado})
    data = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else response
    if not isinstance(data, dict):
        raise ApiError("API response for bem material publicar was not an object")
    return normalize_bem_material(data)


def _normalize_user(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize_text(entry.get("id")),
        "nome": _normalize_text(entry.get("name") or entry.get("nome")),
        "email": _normalize_text(entry.get("email")),
        "perfil": _normalize_text(entry.get("perfil")),
        "classificacao": _normalize_text(entry.get("classificacao")),
        "ativo": bool(entry.get("ativo", True)),
        "criado_em": _normalize_datetime(entry.get("created_at")),
    }


def list_users(
    *, q: str | None = None, perfil: str | None = None, page: int = 1
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params: dict[str, Any] = {"page": page}
    if q:
        params["q"] = q
    if perfil:
        params["perfil"] = perfil
    payload = _request("GET", "/admin/usuarios", params=params)
    items, meta = _unwrap_paginated(payload)
    return [_normalize_user(item) for item in items if isinstance(item, dict)], meta


def update_user_perfil(user_id: str, perfil: str) -> dict[str, Any]:
    response = _request("PATCH", f"/admin/usuarios/{user_id}/perfil", json_body={"perfil": perfil})
    data = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else response
    return data if isinstance(data, dict) else {}


def fetch_curadores() -> list[dict[str, Any]]:
    payload = _request("GET", "/admin/usuarios/curadores")
    data = payload.get("data") if isinstance(payload, dict) else []
    return data if isinstance(data, list) else []


def add_responsavel_bem(bem_id: str, user_id: str, papel: str) -> None:
    _request(
        "POST",
        f"/admin/bens-materiais/{bem_id}/responsaveis",
        json_body={"user_id": user_id, "papel": papel},
    )


def remove_responsavel_bem(bem_id: str, responsavel_id: str) -> None:
    _request("DELETE", f"/admin/bens-materiais/{bem_id}/responsaveis/{responsavel_id}")


def atualizar_curador_responsavel(bem_id: str, curador_responsavel_id: str | None) -> dict[str, Any]:
    response = _request(
        "PATCH",
        f"/admin/bens-materiais/{bem_id}/curador-responsavel",
        json_body={"curador_responsavel_id": curador_responsavel_id},
    )
    data = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else response
    if not isinstance(data, dict):
        raise ApiError("API response for curador responsavel update was not an object")
    return normalize_bem_material(data)


def atualizar_codigo_iphan(bem_id: str, codigo_iphan: str | None) -> dict[str, Any]:
    response = _request(
        "PATCH",
        f"/admin/bens-materiais/{bem_id}/codigo-iphan",
        json_body={"codigo_iphan": codigo_iphan},
    )
    data = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else response
    if not isinstance(data, dict):
        raise ApiError("API response for codigo iphan update was not an object")
    return normalize_bem_material(data)


def excluir_bem_material(bem_id: str) -> None:
    _request("DELETE", f"/admin/bens-materiais/{bem_id}")


def restaurar_auditoria(audit_id: str) -> dict[str, Any]:
    return _request("POST", f"/admin/auditorias/{audit_id}/restaurar")


def _normalize_vinculo_artigo(v: dict[str, Any]) -> dict[str, Any]:
    bem = v.get("bem_material") or {}
    return {
        "id": _normalize_text(v.get("id")),
        "tipo_mencao": _normalize_text(v.get("tipo_mencao")),
        "trecho_relevante": _normalize_text(v.get("trecho_relevante")),
        "bem_material_id": _normalize_text(v.get("bem_material_id")),
        "bem_material": {
            "id": _normalize_text(bem.get("id")),
            "nome_bem": _normalize_text(bem.get("nome_bem")),
            "codigo_iphan": _normalize_text(bem.get("codigo_iphan")),
            "municipio": _normalize_text(bem.get("municipio")),
            "uf": _normalize_text(bem.get("uf")),
        },
    }


def _normalize_autores(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(a.get("nome_autor", "") for a in value if isinstance(a, dict) and a.get("nome_autor"))
    return _normalize_text(value)


def _normalize_artigo(entry: dict[str, Any]) -> dict[str, Any]:
    adicionado_por = entry.get("adicionado_por") or {}
    if isinstance(adicionado_por, dict) and adicionado_por.get("name") and not adicionado_por.get("nome"):
        adicionado_por["nome"] = adicionado_por["name"]
    return {
        "id": _normalize_text(entry.get("id")),
        "titulo": _normalize_text(entry.get("titulo")),
        "doi": _normalize_text(entry.get("doi")),
        "autores": _normalize_autores(entry.get("autores")),
        "ano_publicacao": entry.get("ano_publicacao"),
        "periodico": _normalize_text(entry.get("periodico")),
        "idioma": _normalize_text(entry.get("idioma")),
        "resumo": _normalize_text(entry.get("resumo")),
        "link_acesso": _normalize_text(entry.get("link_acesso")),
        "verificado": bool(entry.get("verificado")),
        "total_vinculos": int(entry.get("vinculos_count") or 0),
        "vinculos": [_normalize_vinculo_artigo(v) for v in (entry.get("vinculos") or [])],
        "created_at": _parse_dt(entry.get("created_at")),
        "updated_at": _parse_dt(entry.get("updated_at")),
        "adicionado_por": adicionado_por if isinstance(adicionado_por, dict) else {},
    }


def list_artigos_admin() -> list[dict[str, Any]]:
    payload = _request("GET", "/admin/artigos-cientificos")
    data = payload.get("data") if isinstance(payload, dict) else payload
    items = data if isinstance(data, list) else []
    return [_normalize_artigo(a) for a in items if isinstance(a, dict)]


def fetch_artigo_admin(artigo_id: str) -> dict[str, Any]:
    payload = _request("GET", f"/admin/artigos-cientificos/{artigo_id}")
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise ApiError("API response for artigo detail was not an object")
    return _normalize_artigo(data)


def excluir_artigo_admin(artigo_id: str) -> None:
    _request("DELETE", f"/admin/artigos-cientificos/{artigo_id}")
