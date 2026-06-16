"""
Views do módulo Curador.

Todo o estado de curadoria e auditoria vive na API Laravel.
Este módulo apenas consome os endpoints /admin/curadorias e /admin/auditorias,
transforma os dados para os templates e envia as decisões de volta via PATCH.

Fluxo:
  curadoria_fila()    → GET /api/v1/admin/curadorias      (só pendentes)
  curadoria_revisao() → busca curadoria na lista paginada
                     → POST /api/v1/admin/curadorias/{id}/avaliar
  audit_logs()        → GET /api/v1/admin/auditorias       (paginado)
  audit_detail()      → busca auditoria por id na lista
"""

from __future__ import annotations

import json
import math
from functools import wraps
from types import SimpleNamespace
from typing import Any

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from api_client.client import (
    ApiError,
    add_responsavel_bem,
    excluir_artigo_admin,
    fetch_all_bens_materiais,
    fetch_all_curadorias,
    fetch_artigo_admin,
    fetch_artigos_por_bem,
    fetch_auditoria,
    fetch_curadores,
    fetch_curadoria,
    invalidate_bens_cache,
    list_artigos_admin,
    list_auditorias,
    list_users,
    normalize_bem_material,
    remove_responsavel_bem,
    restaurar_auditoria,
    update_curadoria_avaliacao,
    update_user_perfil,
)
from pesquisa.models import Usuario

# ─────────────────────────────────────────────────────────────────────────────
# Controle de Acesso
# ─────────────────────────────────────────────────────────────────────────────


def curador_or_admin_required(view_func):
    """Restringe a view a usuários com perfil curador ou admin."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        allowed = {Usuario.PerfilUsuario.CURADOR, Usuario.PerfilUsuario.ADMIN}
        if request.user.is_superuser or getattr(request.user, "perfil", None) in allowed:
            return view_func(request, *args, **kwargs)

        messages.error(request, "Acesso restrito para perfis de curador ou admin.")
        return redirect("home")

    return _wrapped


def admin_required(view_func):
    """Restringe a view exclusivamente a usuários com perfil admin."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        if request.user.is_superuser or getattr(request.user, "perfil", None) == Usuario.PerfilUsuario.ADMIN:
            return view_func(request, *args, **kwargs)

        messages.error(request, "Acesso restrito para administradores.")
        return redirect("home")

    return _wrapped


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de dados
# ─────────────────────────────────────────────────────────────────────────────


def _namespace(value):
    """Converte dict → SimpleNamespace recursivamente (para templates Django)."""
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_namespace(item) for item in value]
    return value


def _to_datetime(value):
    if not value:
        return None
    if hasattr(value, "year"):
        return value
    return parse_datetime(str(value)) or value


def _json_or_text(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def _truncate(value, max_len: int = 72) -> str:
    text = str(value or "")
    return text if len(text) <= max_len else f"{text[: max_len - 3]}..."


def _status_label(status: str) -> str:
    return {
        "pendente": "Pendente",
        "aprovado": "Aprovado",
        "rejeitado": "Rejeitado",
    }.get(str(status or "").lower(), str(status or "").title())


def _field_label(field_name: str) -> str:
    labels = {
        "id": "ID do usuário",
        "nome": "Nome",
        "email": "E-mail",
        "perfil": "Perfil",
        "codigo_iphan": "Código IPHAN",
        "nome_bem": "Nome do bem",
        "nomes_populares": "Nome popular",
        "natureza": "Natureza",
        "tipo": "Tipo",
        "meios_acesso": "Meios de acesso",
        "artefatos": "Artefatos",
        "uf": "Estado (UF)",
        "municipio": "Município",
        "cep": "CEP",
        "endereco": "Endereço",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "geojson": "Geometria (GeoJSON)",
        "ano_registro": "Ano de registro",
        "descricao_atualizacao": "Descrição / Atualização",
        "publicado": "Publicado",
        # ArtigoBemMaterial
        "artigo_titulo": "Título",
        "artigo_autores": "Autores",
        "artigo_doi": "DOI",
        "artigo_periodico": "Periódico",
        "artigo_ano_publicacao": "Ano de publicação",
        "artigo_link_acesso": "Link de acesso",
        "tipo_mencao": "Tipo de menção",
        "trecho_relevante": "Trecho relevante",
    }
    return labels.get(field_name, field_name.replace("_", " ").title())


# ─────────────────────────────────────────────────────────────────────────────
# Geolocalização
# ─────────────────────────────────────────────────────────────────────────────


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _sitios_proximos(lat: float, lng: float, *, raio_km: float = 10.0, excluir_id: str | None = None) -> list[dict]:
    try:
        bens = fetch_all_bens_materiais()
    except ApiError:
        return []

    resultados = []
    for bem in bens:
        if excluir_id and str(bem.get("id")) == str(excluir_id):
            continue
        blat = bem.get("latitude")
        blng = bem.get("longitude")
        if blat is None or blng is None:
            continue
        try:
            dist = _haversine_km(lat, lng, float(blat), float(blng))
        except (TypeError, ValueError):
            continue
        if dist <= raio_km:
            resultados.append({**bem, "distancia_km": dist})

    resultados.sort(key=lambda x: x["distancia_km"])
    return resultados[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Normalização de dados da API
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_user(raw: dict) -> dict:
    """Garante que o dict de usuário tenha a chave 'nome'."""
    user = dict(raw or {})
    if user.get("name") and not user.get("nome"):
        user["nome"] = user["name"]
    return user


def _curadoria_item(raw: dict) -> SimpleNamespace:
    """Transforma um dict de curadoria da API em namespace para o template."""
    entidade_tipo = raw.get("entidade_tipo") or "coleta"
    coleta = raw.get("coleta") or {}
    bem_material = raw.get("bem_material") or {}
    submissao_artigo = raw.get("submissao_artigo") or {}
    usuario = _normalize_user(raw.get("usuario") or {})
    curador = _normalize_user(raw.get("curador") or {})

    display_user = curador or usuario or {"nome": "Equipe de curadoria"}

    if entidade_tipo == "submissao_artigo":
        iphan = bem_material.get("codigo_iphan") or "IPHAN não informado"
        nome = submissao_artigo.get("titulo") or bem_material.get("nome_bem") or "Artigo sem título"
        tipo_label = "Artigo científico"
    else:
        iphan = bem_material.get("codigo_iphan") or coleta.get("codigo_iphan") or "IPHAN não informado"
        nome = coleta.get("nome_bem") or bem_material.get("nome_bem") or "Sem nome informado"
        tipo_label = "Coleta de campo"

    status_display = _status_label(raw.get("status"))
    num_conflitos = _count_field_conflicts(raw) if entidade_tipo == "coleta" else 0

    return _namespace(
        {
            "id": raw.get("id"),
            "entidade_tipo": entidade_tipo,
            "tipo_label": tipo_label,
            "codigo_iphan_display": iphan,
            "nome_display": nome,
            "observacao": raw.get("observacao") or "",
            "num_conflitos": num_conflitos,
            "tem_conflito": num_conflitos > 0,
            "criado_em": _to_datetime(raw.get("created_at") or raw.get("data_avaliacao")),
            "status": raw.get("status") or "pendente",
            "acao_resultante": raw.get("acao_resultante") or "",
            "bem_material_id": raw.get("bem_material_id"),
            "usuario": display_user,
            "coleta": coleta,
            "submissao_artigo": submissao_artigo,
            "bem_material": bem_material,
            "curador": curador,
            "get_status_display": lambda s=status_display: s,
        }
    )


def _incoming_data(curadoria_raw: dict) -> dict:
    """
    Extrai os dados da coleta + dados_coletados como dicionário
    comparável com os campos do BemMaterial.
    """
    coleta = dict(curadoria_raw.get("coleta") or {})
    dados = coleta.get("dados_coletados") or {}
    bem = curadoria_raw.get("bem_material") or {}

    incoming = dict(coleta)
    incoming.update(dados if isinstance(dados, dict) else {})

    # Normaliza aliases entre coleta e bem_material.
    incoming["nome_bem"] = incoming.get("nome_bem") or bem.get("nome_bem") or ""
    incoming["nomes_populares"] = incoming.get("nomes_populares") or bem.get("nomes_populares") or ""
    incoming["codigo_iphan"] = bem.get("codigo_iphan") or incoming.get("codigo_iphan") or ""
    incoming["natureza"] = incoming.get("natureza_bem") or incoming.get("natureza") or bem.get("natureza") or ""
    incoming["tipo"] = incoming.get("tipo_bem") or incoming.get("tipo") or bem.get("tipo") or ""
    incoming["meios_acesso"] = incoming.get("meios_acesso") or bem.get("meios_acesso") or ""
    incoming["artefatos"] = incoming.get("artefatos") or bem.get("artefatos") or []
    incoming["uf"] = incoming.get("uf") or bem.get("uf") or ""
    incoming["municipio"] = incoming.get("municipio") or bem.get("municipio") or ""
    incoming["cep"] = incoming.get("cep") or bem.get("cep") or ""
    incoming["endereco"] = incoming.get("endereco") or bem.get("endereco") or ""
    incoming["latitude"] = incoming.get("latitude") or bem.get("latitude") or ""
    incoming["longitude"] = incoming.get("longitude") or bem.get("longitude") or ""
    incoming["geojson"] = incoming.get("geojson") or bem.get("geojson") or {}
    incoming["ano_registro"] = incoming.get("ano_registro") or bem.get("ano_registro")
    incoming["descricao_atualizacao"] = (
        incoming.get("descricao") or incoming.get("descricao_atualizacao") or bem.get("descricao_atualizacao") or ""
    )
    return incoming


def _build_comparisons(curadoria_raw: dict) -> list[dict]:
    """
    Compara dados da coleta (incoming) com o bem_material oficial.

    Retorna apenas campos que diferem ou que são novos.
    As chaves retornadas correspondem exatamente ao que o template espera:
      incoming_value  — valor vindo da coleta
      official_value  — valor no registro oficial (vazio se não existir)
      is_new_field    — True quando o campo era null/vazio no bem oficial
      is_different    — True quando os valores diferem (inclui is_new_field)
    """
    incoming = _incoming_data(curadoria_raw)
    official_raw = curadoria_raw.get("bem_material") or {}
    official = normalize_bem_material(official_raw) if official_raw else {}
    is_new_record = not bool(official_raw)

    field_order = [
        "codigo_iphan",
        "nome_bem",
        "nomes_populares",
        "natureza",
        "tipo",
        "artefatos",
        "meios_acesso",
        "uf",
        "municipio",
        "cep",
        "endereco",
        "latitude",
        "longitude",
        "geojson",
        "ano_registro",
        "descricao_atualizacao",
    ]

    comparisons = []
    for field in field_order:
        official_val = _json_or_text(official.get(field))
        incoming_val = _json_or_text(incoming.get(field))

        # Omite linhas em que ambos são vazios.
        if not official_val and not incoming_val:
            continue
        # Omite linhas idênticas (exceto campos-chave sempre exibidos).
        if official_val == incoming_val and field not in ("codigo_iphan", "nome_bem"):
            continue

        # Campo novo: não existia (ou era vazio) no registro oficial.
        is_new_field = is_new_record or (not official_val and bool(incoming_val))
        is_different = official_val != incoming_val

        comparisons.append(
            {
                "field_name": field,
                "label": _field_label(field),
                # Chaves que o template usa:
                "incoming_value": incoming_val,
                "official_value": official_val,
                "is_new_field": is_new_field,
                "is_different": is_different,
                # Aliases para retrocompatibilidade:
                "new_value": incoming_val,
                "old_value": official_val,
                "changed": is_different,
            }
        )

    return comparisons


def _count_field_conflicts(curadoria_raw: dict) -> int:
    """
    Conta campos que diferem entre a coleta e o registro oficial.
    Um conflito real é quando o campo já existia no bem e o valor proposto é diferente.
    Retorna 0 para novos sítios (sem bem_material) — lá não há conflito, só inserção.
    """
    bem = curadoria_raw.get("bem_material") or {}
    if not bem:
        return 0

    try:
        comparisons = _build_comparisons(curadoria_raw)
        return sum(1 for c in comparisons if c["is_different"] and not c["is_new_field"])
    except Exception:
        return 0


def _audit_entry(raw: dict) -> SimpleNamespace:
    """Transforma um dict de auditoria da API em namespace."""
    usuario = _normalize_user(raw.get("usuario") or {})
    curadoria = raw.get("curadoria") or {}

    return _namespace(
        {
            "id": raw.get("id"),
            "usuario": usuario,
            "entidade_tipo": raw.get("entidade_tipo"),
            "entidade_id": raw.get("entidade_id"),
            "curadoria_id": raw.get("curadoria_id"),
            "operacao": raw.get("operacao"),
            "meio": raw.get("meio"),
            "data_hora": _to_datetime(raw.get("data_hora") or raw.get("created_at")),
            "valor_anterior": raw.get("valor_anterior") or {},
            "valor_novo": raw.get("valor_novo") or {},
            "curadoria": curadoria,
        }
    )


def _op_class(operacao: str) -> str:
    op = str(operacao or "").lower()
    if any(x in op for x in ("inser", "cria", "novo")):
        return "op-create"
    if any(x in op for x in ("exclu", "remov", "delet")):
        return "op-delete"
    if any(x in op for x in ("valid", "aprov")):
        return "op-validate"
    return "op-update"


# Campos que aparecem sempre no detalhe de auditoria (contexto do registro),
# mesmo que não tenham sido modificados nessa operação.
_AUDIT_ALWAYS_SHOW = {"nome_bem", "natureza", "tipo", "publicado", "artigo_titulo", "id", "nome", "email"}

# Ordem preferencial de exibição dos campos na tabela de auditoria.
_AUDIT_FIELD_ORDER = [
    # Usuário (contexto de alteração de perfil)
    "id",
    "nome",
    "email",
    "perfil",
    # BemMaterial
    "nome_bem",
    "natureza",
    "tipo",
    "publicado",
    "nomes_populares",
    "artefatos",
    "meios_acesso",
    "uf",
    "municipio",
    "cep",
    "endereco",
    "latitude",
    "longitude",
    "ano_registro",
    "descricao_atualizacao",
    # ArtigoBemMaterial
    "artigo_titulo",
    "artigo_autores",
    "artigo_doi",
    "artigo_periodico",
    "artigo_ano_publicacao",
    "artigo_link_acesso",
    "tipo_mencao",
    "trecho_relevante",
]


_SNAP_FIELDS = [
    # BemMaterial
    "nome_bem", "codigo_iphan", "nomes_populares", "natureza", "tipo",
    "artefatos", "publicado", "ano_registro", "descricao_atualizacao",
    "municipio", "uf", "cep", "endereco", "latitude", "longitude", "meios_acesso",
    # ArtigoBemMaterial
    "artigo_titulo", "artigo_autores", "artigo_doi", "artigo_periodico",
    "artigo_ano_publicacao", "artigo_link_acesso", "tipo_mencao", "trecho_relevante",
]

_ENTITY_ARTIGO = "ArtigoBemMaterial"

# Campos da coleta que queremos listar na visão de "coleta vs aprovado".
_BEM_COLETA_FIELDS = [
    "nome_bem", "natureza", "tipo", "nomes_populares", "artefatos",
    "meios_acesso", "uf", "municipio", "cep", "endereco",
    "latitude", "longitude", "ano_registro", "descricao_atualizacao",
]


def _build_merged_snap(audit_ns) -> tuple[SimpleNamespace, SimpleNamespace]:
    """
    Retorna (snap_merged, snap_changed).

    snap_merged : estado resultante — valor_anterior com valor_novo sobreposto.
    snap_changed: namespace de booleanos (True = campo veio do valor_novo).

    Para Inserção (valor_anterior nulo): snap_merged = valor_novo, tudo False.
    Para Alteração: campos de valor_novo aparecem destacados (True).
    """
    def _as_dict(v):
        if isinstance(v, dict):
            return v
        if isinstance(v, SimpleNamespace):
            return vars(v)
        return {}

    before = _as_dict(getattr(audit_ns, "valor_anterior", {}))
    after  = _as_dict(getattr(audit_ns, "valor_novo",    {}))
    base   = before if before else after

    merged:  dict = {}
    changed: dict = {}

    for f in _SNAP_FIELDS:
        in_novo = f in after and after.get(f) is not None
        if in_novo:
            merged[f]  = after[f]
            changed[f] = bool(before)   # True só se havia estado anterior
        else:
            merged[f]  = base.get(f, None)
            changed[f] = False

    return _namespace(merged), _namespace(changed)


def _build_audit_snap(audit_ns) -> SimpleNamespace:
    """
    Retorna um SimpleNamespace com todos os campos do snapshot normalizados.

    Prioridade: valor_anterior (snapshot completo para Alteração/Exclusão).
    Fallback:   valor_novo (snapshot para Inserção, onde anterior é null).
    Campos ausentes ficam como None — nunca levantam VariableDoesNotExist no template.
    """
    def _as_dict(v):
        if isinstance(v, dict):
            return v
        if isinstance(v, SimpleNamespace):
            return vars(v)
        return {}

    before = _as_dict(getattr(audit_ns, "valor_anterior", {}))
    after = _as_dict(getattr(audit_ns, "valor_novo", {}))

    # Usa valor_anterior se tiver dados; senão cai em valor_novo (caso Inserção).
    base = before if before else after
    # Complementa campos ausentes com valor_novo como fallback secundário.
    merged = {f: base.get(f, after.get(f, None)) for f in _SNAP_FIELDS}
    return _namespace(merged)


def _field_comparisons_from_audit(audit_ns) -> list[dict]:
    """
    Extrai comparações campo-a-campo de um registro de auditoria.

    Regras:
    - Campos em valor_novo (foram explicitamente alterados): sempre exibidos,
      com old_value ≠ new_value e changed=True.
    - Campos básicos (_AUDIT_ALWAYS_SHOW) que existem no valor_anterior mas
      NÃO foram alterados: exibidos com changed=False para dar contexto.
    - Demais campos do snapshot anterior que não foram tocados: omitidos.
    """

    def _as_dict(v):
        if isinstance(v, dict):
            return v
        if isinstance(v, SimpleNamespace):
            return vars(v)
        return {}

    before = _as_dict(getattr(audit_ns, "valor_anterior", {}))
    after = _as_dict(getattr(audit_ns, "valor_novo", {}))

    keys_changed = set(after.keys())
    keys_always = _AUDIT_ALWAYS_SHOW & (set(before.keys()) | set(after.keys()))
    keys_to_show = keys_changed | keys_always

    ordered = [f for f in _AUDIT_FIELD_ORDER if f in keys_to_show]
    ordered += sorted(keys_to_show - set(_AUDIT_FIELD_ORDER))

    comparisons = []
    for field in ordered:
        old_val = _json_or_text(before.get(field, ""))

        if field in after:
            new_val = _json_or_text(after[field])
        else:
            # Campo de contexto (always-show) não modificado — mesmo valor dos dois lados.
            new_val = old_val

        comparisons.append(
            {
                "field_name": field,
                "label": _field_label(field),
                "old_value": old_val,
                "new_value": new_val,
                "changed": old_val != new_val,
            }
        )

    return comparisons


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────


@curador_or_admin_required
def curadoria_fila(request):
    """
    Lista curadorias com status 'pendente' vindas da API.
    Filtros aplicados localmente após fetch completo.
    """
    query = request.GET.get("q", "").strip().lower()
    filtro_tipo = request.GET.get("tipo", "").strip()
    filtro_destino = request.GET.get("destino", "").strip()
    filtro_conflito = request.GET.get("conflito", "").strip()
    filtro_meu = request.GET.get("meu_responsavel", "").strip() == "1"

    current_filters = {
        "q": request.GET.get("q", "").strip(),
        "tipo": filtro_tipo,
        "destino": filtro_destino,
        "conflito": filtro_conflito,
        "meu_responsavel": "1" if filtro_meu else "",
    }

    try:
        curadorias = [
            _curadoria_item(item)
            for item in fetch_all_curadorias()
            if str(item.get("status") or "").lower() == "pendente"
        ]
    except ApiError:
        curadorias = []
        messages.warning(request, "Não foi possível carregar as curadorias da API.")

    total_antes_filtro = len(curadorias)
    total_conflitos = len([c for c in curadorias if c.tem_conflito])

    # -- busca textual
    if query:
        def _usuario_nome(c):
            u = c.usuario
            if not u:
                return ""
            if isinstance(u, dict):
                return u.get("nome") or u.get("name") or ""
            return getattr(u, "nome", None) or getattr(u, "name", "") or ""

        curadorias = [
            c for c in curadorias
            if query in str(c.codigo_iphan_display).lower()
            or query in str(c.nome_display).lower()
            or query in str(c.observacao).lower()
            or query in str(c.tipo_label).lower()
            or query in _usuario_nome(c).lower()
        ]

    # -- tipo: coleta ou artigo
    if filtro_tipo == "coleta":
        curadorias = [c for c in curadorias if c.entidade_tipo == "coleta"]
    elif filtro_tipo == "artigo":
        curadorias = [c for c in curadorias if c.entidade_tipo == "submissao_artigo"]

    # -- destino: novo sítio (sem bem_material_id) ou sítio existente (com)
    if filtro_destino == "novo_sitio":
        curadorias = [c for c in curadorias if not c.bem_material_id]
    elif filtro_destino == "sitio_existente":
        curadorias = [c for c in curadorias if c.bem_material_id]

    # -- conflito (baseado em diferenças reais de campo, não na observação do curador)
    if filtro_conflito == "sim":
        curadorias = [c for c in curadorias if c.tem_conflito]
    elif filtro_conflito == "nao":
        curadorias = [c for c in curadorias if not c.tem_conflito]

    # -- responsável: filtra sítios onde o usuário logado é curador responsável
    if filtro_meu:
        user_email = getattr(request.user, "email", "")
        def _is_meu(c):
            bem = c.bem_material
            if not bem:
                return False
            resp = bem.get("curador_responsavel") if isinstance(bem, dict) else getattr(bem, "curador_responsavel", None)
            if not resp:
                return False
            if isinstance(resp, dict):
                return resp.get("email") == user_email
            return getattr(resp, "email", None) == user_email
        curadorias = [c for c in curadorias if _is_meu(c)]

    sort = request.GET.get("sort", "criado_em")
    sort_dir = request.GET.get("dir", "desc")
    if sort not in ("nome", "criado_em"):
        sort = "criado_em"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    if sort == "nome":
        curadorias.sort(key=lambda c: (c.nome_display or "").lower(), reverse=(sort_dir == "desc"))
    else:
        curadorias.sort(
            key=lambda c: c.criado_em.isoformat() if c.criado_em else "",
            reverse=(sort_dir == "desc"),
        )

    def _sort_url(col: str) -> str:
        new_dir = "desc" if (sort == col and sort_dir == "asc") else "asc"
        qs = request.GET.copy()
        qs["sort"] = col
        qs["dir"] = new_dir
        qs.pop("page", None)
        return "?" + qs.urlencode()

    def _sort_arrow(col: str) -> str:
        if sort != col:
            return "⇅"
        return "▲" if sort_dir == "asc" else "▼"

    sort_cols = {
        "nome": {"url": _sort_url("nome"), "arrow": _sort_arrow("nome"), "active": sort == "nome"},
        "criado_em": {"url": _sort_url("criado_em"), "arrow": _sort_arrow("criado_em"), "active": sort == "criado_em"},
    }

    paginator = Paginator(curadorias, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "curador/curadoria_fila.html",
        {
            "nav_active": "curadoria",
            "page_obj": page_obj,
            "current_filters": current_filters,
            "total_pendentes": total_antes_filtro,
            "total_filtrado": len(curadorias),
            "conflitos": total_conflitos,
            "sort": sort,
            "sort_dir": sort_dir,
            "sort_cols": sort_cols,
        },
    )


def _handle_revisao_artigo(request, curadoria_id: str, curadoria_raw: dict):
    """
    Lida com revisão de submissão de artigo científico (entidade_tipo='submissao_artigo').
    Chamado internamente por curadoria_revisao() após detecção do tipo.
    """
    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "rejeitar":
            payload: dict = {
                "status": "rejeitado",
                "acao_resultante": "rejeitar",
                "observacao": request.POST.get("observacao") or None,
            }
        elif action == "aprovar_artigo":
            payload = {
                "status": "aprovado",
                "acao_resultante": "aprovar",
                "observacao": request.POST.get("observacao") or None,
            }
        else:
            messages.error(request, "Ação desconhecida.")
            return redirect("curadoria-revisao", curadoria_id=curadoria_id)

        try:
            update_curadoria_avaliacao(curadoria_id, payload)
            invalidate_bens_cache()
            messages.success(request, "Curadoria avaliada com sucesso.")
        except ApiError as exc:
            messages.error(request, f"Não foi possível atualizar a curadoria: {exc}")
            return redirect("curadoria-revisao", curadoria_id=curadoria_id)

        return redirect("curadoria-fila")

    # ── GET ──────────────────────────────────────────────────────────────────
    submissao = curadoria_raw.get("submissao_artigo") or {}
    bem_material_raw = curadoria_raw.get("bem_material") or {}

    request_user = (
        getattr(request.user, "nome", None)
        or getattr(request.user, "name", None)
        or getattr(request.user, "email", None)
        or "Equipe de curadoria"
    )

    curadoria_ctx = _namespace(
        {
            "id": curadoria_raw.get("id"),
            "usuario": {"nome": request_user},
            "observacao": curadoria_raw.get("observacao") or "",
            "status": curadoria_raw.get("status") or "pendente",
            "acao_resultante": curadoria_raw.get("acao_resultante") or "",
        }
    )

    tipo_mencao_labels = {
        "citacao": "Citação direta",
        "estudo_aprofundado": "Estudo aprofundado",
        "referencia_geografica": "Referência geográfica",
        "analise_artefatos": "Análise de artefatos",
    }
    tipo_mencao_raw = submissao.get("tipo_mencao") or ""
    tipo_mencao_label = tipo_mencao_labels.get(tipo_mencao_raw, tipo_mencao_raw)

    # Verifica se já existe vínculo entre este artigo e o bem material.
    # Só faz a chamada quando ambos os IDs estão disponíveis (artigo já cadastrado).
    vinculo_existente = False
    artigo_id_submissao = submissao.get("artigo_id")
    bem_id = bem_material_raw.get("id") if bem_material_raw else None
    if artigo_id_submissao and bem_id:
        try:
            artigos_do_bem = fetch_artigos_por_bem(bem_id)
            vinculo_existente = any(str(a.get("id")) == str(artigo_id_submissao) for a in artigos_do_bem)
        except ApiError:
            pass

    return render(
        request,
        "curador/curadoria_revisao_artigo.html",
        {
            "nav_active": "curadoria",
            "curadoria": curadoria_ctx,
            "submissao": _namespace(submissao),
            "tipo_mencao_label": tipo_mencao_label,
            "bem_material": _namespace(normalize_bem_material(bem_material_raw)) if bem_material_raw else None,
            "bem_material_raw": bem_material_raw,
            "vinculo_existente": vinculo_existente,
        },
    )


@curador_or_admin_required
def curadoria_revisao(request, curadoria_id):
    """
    Exibe o split-screen de revisão de uma curadoria e processa a decisão.

    GET  — exibe comparação entre os dados da coleta e o bem_material oficial.
    POST — envia a avaliação para PATCH /admin/curadorias/{id}/avaliar.

    Enum values esperados pela API (camelCase):
      acao_resultante: criarSitio | atualizarSitio | rejeitar | aprovar
      status:          aprovado   | rejeitado
    """
    try:
        curadoria_raw = fetch_curadoria(curadoria_id)
    except ApiError:
        raise Http404("Curadoria não encontrada")

    # Curadorias de submissão de artigo têm tela de revisão própria.
    entidade_tipo = curadoria_raw.get("entidade_tipo") or "coleta"
    if entidade_tipo == "submissao_artigo":
        return _handle_revisao_artigo(request, curadoria_id, curadoria_raw)

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "add_responsavel":
            bem_id = curadoria_raw.get("bem_material_id") or ""
            if bem_id:
                try:
                    add_responsavel_bem(bem_id, request.POST.get("user_id") or "", request.POST.get("papel") or "")
                except ApiError as exc:
                    messages.error(request, f"Não foi possível adicionar responsável: {exc}")
            return redirect("curadoria-revisao", curadoria_id=curadoria_id)

        elif action == "remove_responsavel":
            bem_id = curadoria_raw.get("bem_material_id") or ""
            if bem_id:
                try:
                    remove_responsavel_bem(bem_id, request.POST.get("responsavel_id") or "")
                except ApiError as exc:
                    messages.error(request, f"Não foi possível remover responsável: {exc}")
            return redirect("curadoria-revisao", curadoria_id=curadoria_id)

        elif action == "rejeitar":
            payload = {
                "status": "rejeitado",
                "acao_resultante": "rejeitar",
                "observacao": request.POST.get("observacao") or None,
            }

        elif action == "aprovar_mesclar":
            # Se a curadoria já tem bem_material_id → atualiza o bem existente.
            # Caso contrário → cria novo sítio.
            bem_id = request.POST.get("bem_material_id") or curadoria_raw.get("bem_material_id") or None
            acao = "atualizarSitio" if bem_id else "criarSitio"
            publicado = request.POST.get("published_selected", "0") == "1"

            payload = {
                "status": "aprovado",
                "acao_resultante": acao,
                "observacao": request.POST.get("observacao") or None,
                "publicado": publicado,
            }
            if acao == "atualizarSitio":
                payload["bem_material_id"] = bem_id

            # Campos selecionados pelo curador — aplicado tanto em criarSitio
            # quanto em atualizarSitio para respeitar a seleção do curador.
            _all_fields = [
                "nome_bem", "nomes_populares", "natureza", "tipo", "artefatos",
                "meios_acesso", "uf", "municipio", "cep", "endereco",
                "latitude", "longitude", "ano_registro", "descricao_atualizacao",
            ]

            try:
                selected_field_names = json.loads(request.POST.get("selected_fields", "[]"))
                if not isinstance(selected_field_names, list):
                    selected_field_names = []
            except (ValueError, TypeError):
                selected_field_names = []

            incoming = _incoming_data(curadoria_raw)

            if selected_field_names:
                campos = {
                    f: incoming.get(f)
                    for f in selected_field_names
                    if f in incoming and incoming.get(f) not in (None, "", [])
                }
            else:
                campos = {f: incoming.get(f) for f in _all_fields if incoming.get(f) not in (None, "", [])}

            if campos:
                payload["campos"] = campos

        else:
            messages.error(request, "Ação desconhecida.")
            return redirect("curadoria-revisao", curadoria_id=curadoria_id)

        try:
            update_curadoria_avaliacao(curadoria_id, payload)
            # Invalida o cache de bens materiais para que o mapa e a lista
            # reflitam imediatamente o novo/atualizado sítio sem reiniciar o servidor.
            invalidate_bens_cache()
            messages.success(request, "Curadoria avaliada com sucesso.")
        except ApiError as exc:
            messages.error(request, f"Não foi possível atualizar a curadoria: {exc}")
            return redirect("curadoria-revisao", curadoria_id=curadoria_id)

        return redirect("curadoria-fila")

    # ── GET ──────────────────────────────────────────────────────────────────
    incoming_data = _incoming_data(curadoria_raw)
    official_site_raw = curadoria_raw.get("bem_material") or {}
    official_record_exists = bool(official_site_raw)
    official_site = _namespace(normalize_bem_material(official_site_raw)) if official_site_raw else None
    comparisons = _build_comparisons(curadoria_raw)

    # Sítios próximos às coordenadas da coleta (para sugestão de associação).
    sitios_proximos: list[dict] = []
    coleta_lat = incoming_data.get("latitude")
    coleta_lng = incoming_data.get("longitude")
    if coleta_lat and coleta_lng:
        try:
            sitios_proximos = _sitios_proximos(
                float(coleta_lat),
                float(coleta_lng),
                excluir_id=curadoria_raw.get("bem_material_id"),
            )
        except (TypeError, ValueError):
            pass

    # Auditorias relacionadas à curadoria.
    audit_entries = []
    page = 1
    while True:
        try:
            items, meta = list_auditorias(
                entidade_tipo="App\\Models\\Curadoria",
                entidade_id=curadoria_id,
                page=page,
            )
        except ApiError:
            break
        audit_entries.extend(_audit_entry(item) for item in items)
        if page >= int(meta.get("pages") or 1):
            break
        page += 1

    request_user = (
        getattr(request.user, "nome", None)
        or getattr(request.user, "name", None)
        or getattr(request.user, "email", None)
        or "Equipe de curadoria"
    )

    curadoria_ctx = _namespace(
        {
            "id": curadoria_raw.get("id"),
            "usuario": {"nome": request_user},
            "observacao": curadoria_raw.get("observacao") or "",
            "status": curadoria_raw.get("status") or "pendente",
            "acao_resultante": curadoria_raw.get("acao_resultante") or "",
        }
    )

    _avatar_colors = ["#22C55E", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#BA9F8B"]
    responsaveis_bem = []
    for i, r in enumerate(official_site_raw.get("responsaveis") or []):
        if not isinstance(r, dict):
            continue
        u = r.get("usuario") or {}
        if isinstance(u, dict) and "data" in u:
            u = u.get("data") or {}
        nome = u.get("name") or u.get("nome") or ""
        palavras = nome.split()
        iniciais = ("".join(p[0].upper() for p in palavras[:2])) if palavras else "?"
        responsaveis_bem.append({
            "id": r.get("id") or "",
            "user_id": r.get("user_id") or "",
            "papel": r.get("papel") or "",
            "nome": nome,
            "email": u.get("email") or "",
            "iniciais": iniciais,
            "cor": _avatar_colors[i % len(_avatar_colors)],
        })

    curadores_list: list[dict] = []
    try:
        curadores_list = fetch_curadores()
    except ApiError:
        pass

    iphan = official_site_raw.get("codigo_iphan") or incoming_data.get("codigo_iphan") or "IPHAN não informado"

    return render(
        request,
        "curador/curadoria_revisao.html",
        {
            "nav_active": "curadoria",
            "curadoria": curadoria_ctx,
            "codigo_iphan": iphan,
            "display_nome": incoming_data.get("nome_bem") or "Novo registro sem nome",
            "official_site": official_site,
            "official_record_exists": official_record_exists,
            "comparisons": comparisons,
            "incoming_data": incoming_data,
            "audit_entries": audit_entries,
            "merged": request.GET.get("merged") == "1",
            "default_published": bool(official_site_raw.get("publicado")) if official_site_raw else False,
            "sitios_proximos": sitios_proximos,
            "sitios_proximos_json": json.dumps(
                [
                    {k: v for k, v in s.items() if not isinstance(v, (dict, list)) or k in ("artefatos",)}
                    for s in sitios_proximos
                ],
                ensure_ascii=False,
                default=str,
            ),
            "responsaveis_bem": responsaveis_bem,
            "curadores_list": curadores_list,
            "bem_material_id_inicial": curadoria_raw.get("bem_material_id") or "",
        },
    )


_AUDIT_ENTIDADE_MAP = {
    "criacao_sitio":       "App\\Models\\BemMaterial",
    "exclusao_sitio":      "App\\Models\\BemMaterial",
    "alteracao":           "App\\Models\\BemMaterial",
    "sitios":              "App\\Models\\BemMaterial",
    "artigos":             "App\\Models\\ArtigoBemMaterial",
    "aprovacoes_sitio":    "App\\Models\\Curadoria",
    "aprovacoes_artigo":   "App\\Models\\SubmissaoArtigo",
}

_AUDIT_OP_FILTER = {
    "criacao_sitio":  lambda op: "inser" in op.lower(),
    "exclusao_sitio": lambda op: "exclus" in op.lower(),
    "alteracao":      lambda op: "altera" in op.lower(),
}


@curador_or_admin_required
def audit_logs(request):
    """
    Lista paginada de auditorias via GET /admin/auditorias.
    Filtros de tipo enviados para a API; filtros de operação aplicados localmente.
    """
    query = request.GET.get("q", "").strip().lower()
    filtro = request.GET.get("filtro", "").strip()
    responsavel_q = request.GET.get("responsavel", "").strip().lower()
    curadoria_id_q = request.GET.get("curadoria_id", "").strip()
    page = max(1, int(request.GET.get("page", 1) or 1))

    current_filters = {
        "q": request.GET.get("q", "").strip(),
        "filtro": filtro,
        "responsavel": request.GET.get("responsavel", "").strip(),
        "curadoria_id": curadoria_id_q,
    }

    if curadoria_id_q:
        entidade_tipo_param = "App\\Models\\Curadoria"
        entidade_id_param = curadoria_id_q
    else:
        entidade_tipo_param = _AUDIT_ENTIDADE_MAP.get(filtro)
        entidade_id_param = None

    try:
        items, meta = list_auditorias(
            page=page,
            entidade_tipo=entidade_tipo_param,
            entidade_id=entidade_id_param,
        )
    except ApiError:
        items, meta = [], {"total": 0, "page": 1, "pages": 1, "per_page": 50}

    entries = []
    for item in items:
        user = _normalize_user(item.get("usuario") or {})
        op = item.get("operacao") or ""
        before = item.get("valor_anterior") or {}
        after = item.get("valor_novo") or {}

        entidade_tipo = item.get("entidade_tipo") or ""
        is_artigo = _ENTITY_ARTIGO in entidade_tipo
        is_curadoria = "Curadoria" in entidade_tipo

        # Labels especiais por tipo de entidade + operação.
        op_lower = op.lower()
        if is_artigo and "remo" in op_lower:
            op_label = "REMOÇÃO-ARTIGO"
        elif is_artigo and "inser" in op_lower:
            op_label = "VÍNCULO-ARTIGO"
        elif is_curadoria and "rejei" in op_lower:
            op_label = "REJEIÇÃO"
        else:
            op_label = op.replace("_", " ").upper() or "ATUALIZAR"

        # Target legível.
        artigo_titulo = (before or after).get("artigo_titulo") if isinstance(before or after, dict) else None
        nome_bem = (before or after).get("nome_bem") if isinstance(before or after, dict) else None
        if is_artigo and artigo_titulo:
            target = _truncate(artigo_titulo, 60)
        elif is_curadoria and nome_bem:
            target = _truncate(nome_bem, 60)
        else:
            target = (
                f"{entidade_tipo} #{item.get('entidade_id')}"
                if item.get("entidade_id")
                else entidade_tipo
            )

        entries.append(
            {
                "audit_id": item.get("id"),
                "created_at": _to_datetime(item.get("data_hora") or item.get("created_at")),
                "user_name": user.get("nome") or user.get("name") or user.get("email") or "Sistema",
                "operation": op,
                "operation_label": op_label,
                "operation_class": _op_class(op),
                "entity": entidade_tipo,
                "target": target,
                "before": before,
                "after": after,
                "before_preview": _truncate(json.dumps(before, ensure_ascii=False)),
                "after_preview": _truncate(json.dumps(after, ensure_ascii=False)),
            }
        )

    # -- filtro de operação (client-side, complementar ao filtro de entidade da API)
    if filtro in _AUDIT_OP_FILTER:
        op_fn = _AUDIT_OP_FILTER[filtro]
        entries = [e for e in entries if op_fn(e["operation"])]

    # -- busca textual
    if query:
        entries = [
            e for e in entries
            if query in str(e["user_name"]).lower()
            or query in str(e["operation_label"]).lower()
            or query in str(e["entity"]).lower()
            or query in str(e["target"]).lower()
            or query in str(e.get("before_preview") or "").lower()
            or query in str(e.get("after_preview") or "").lower()
        ]

    # -- filtro por responsável (nome do usuário)
    if responsavel_q:
        entries = [e for e in entries if responsavel_q in str(e["user_name"]).lower()]

    paginator = Paginator(entries, meta.get("per_page", 50))
    page_obj = paginator.get_page(meta.get("page", 1))

    return render(
        request,
        "curador/audit_logs.html",
        {
            "nav_active": "audit",
            "page_obj": page_obj,
            "current_filters": current_filters,
            "total_logs": meta.get("total", len(entries)),
            "sync_status": "NOMINAL",
            "total_users": len({e["user_name"] for e in entries}),
            "api_page": meta.get("page", 1),
            "api_pages": meta.get("pages", 1),
        },
    )


@curador_or_admin_required
def audit_detail(request, audit_id):
    """
    Exibe os detalhes de um registro de auditoria com comparação lado a lado.

    Nota: a API não tem endpoint GET /auditorias/{id}.
    fetch_auditoria() itera as páginas para encontrar o registro.
    (Ver lista de futuras implementações.)
    """
    try:
        raw = fetch_auditoria(audit_id)
    except ApiError:
        raise Http404("Registro de auditoria não encontrado")

    audit_ns = _audit_entry(raw)

    # Tenta enriquecer com dados da curadoria, se vinculada.
    curadoria_raw_full: dict = {}
    if raw.get("curadoria_id"):
        try:
            curadoria_raw_full = fetch_curadoria(raw["curadoria_id"])
            audit_ns.curadoria = _namespace(
                {
                    "observacao": curadoria_raw_full.get("observacao") or "",
                    "status": curadoria_raw_full.get("status") or "",
                }
            )
        except ApiError:
            audit_ns.curadoria = _namespace({"observacao": "", "status": ""})

    comparisons = _field_comparisons_from_audit(audit_ns)
    snap = _build_audit_snap(audit_ns)
    snap_merged, snap_changed = _build_merged_snap(audit_ns)

    # valor_anterior é null em operações de Inserção — não existe snapshot anterior.
    raw_anterior = raw.get("valor_anterior")
    snap_has_anterior = bool(raw_anterior) if raw_anterior is not None else False

    # Para auditorias de BemMaterial ou Rejeição com curadoria vinculada,
    # monta a lista de campos da coleta com indicação de aprovação por campo.
    field_status: list[dict] | None = None
    entidade_tipo = raw.get("entidade_tipo") or ""
    is_bem_material   = curadoria_raw_full and "BemMaterial" in entidade_tipo and _ENTITY_ARTIGO not in entidade_tipo
    is_rejeicao       = curadoria_raw_full and "Curadoria"   in entidade_tipo

    if is_bem_material or is_rejeicao:
        try:
            incoming = _incoming_data(curadoria_raw_full)
            valor_novo = raw.get("valor_novo") or {}
            if isinstance(valor_novo, SimpleNamespace):
                valor_novo = vars(valor_novo)

            field_status = []
            for field in _BEM_COLETA_FIELDS:
                coleta_val = _json_or_text(incoming.get(field))
                if not coleta_val:
                    continue

                if is_rejeicao:
                    # Rejeição: nenhum campo foi aplicado
                    estado = "rejeitado"
                elif bool(valor_novo.get(field) is not None and _json_or_text(valor_novo.get(field))):
                    estado = "aprovado"
                else:
                    estado = "nao_aplicado"

                field_status.append(
                    {
                        "label": _field_label(field),
                        "field_name": field,
                        "coleta_value": coleta_val,
                        "estado": estado,
                    }
                )
        except Exception:
            field_status = None

    restaurar_url = None
    entidade_tipo_raw = raw.get("entidade_tipo") or ""
    operacao_raw = raw.get("operacao") or ""
    _OPERACOES_REVERTIVEIS = {"insercao", "alteracao", "Inserção", "Alteração"}
    if "BemMaterial" in entidade_tipo_raw and operacao_raw in _OPERACOES_REVERTIVEIS:
        restaurar_url = reverse("restaurar-auditoria", kwargs={"audit_id": raw.get("id")})

    return render(
        request,
        "curador/audit_detail.html",
        {
            "nav_active": "audit",
            "audit_entry": audit_ns,
            "comparisons": comparisons,
            "field_status": field_status,
            "audit_id": raw.get("id"),
            "snap": snap,
            "snap_merged": snap_merged,
            "snap_changed": snap_changed,
            "snap_has_anterior": snap_has_anterior,
            "restaurar_url": restaurar_url,
        },
    )


@curador_or_admin_required
@require_POST
def restaurar_auditoria_view(request, audit_id: str):
    try:
        restaurar_auditoria(audit_id)
        invalidate_bens_cache()
        messages.success(request, "Reversão realizada com sucesso.")
    except ApiError as exc:
        messages.error(request, f"Não foi possível reverter: {exc}")
    return redirect("audit-detail", audit_id=audit_id)


# ─────────────────────────────────────────────────────────────────────────────
# Artigos Científicos
# ─────────────────────────────────────────────────────────────────────────────

_TIPO_MENCAO_LABELS = {
    "citacao": "Citação direta",
    "estudo_aprofundado": "Estudo aprofundado",
    "referencia_geografica": "Referência geográfica",
    "analise_artefatos": "Análise de artefatos",
}

_ARTIGOS_SORT_KEYS: dict[str, Any] = {
    "titulo":      lambda a: (a.get("titulo") or "").lower(),
    "mencoes":     lambda a: a.get("total_vinculos") or 0,
    "ano":         lambda a: a.get("ano_publicacao") or 0,
    "modificacao": lambda a: str(a.get("updated_at") or ""),
}


@curador_or_admin_required
def artigos_lista(request):
    sort = request.GET.get("sort", "titulo")
    direction = request.GET.get("dir", "asc")
    if sort not in _ARTIGOS_SORT_KEYS:
        sort = "titulo"
    if direction not in ("asc", "desc"):
        direction = "asc"

    try:
        artigos = list_artigos_admin()
    except ApiError:
        artigos = []
        messages.warning(request, "Não foi possível carregar os artigos.")

    artigos = sorted(artigos, key=_ARTIGOS_SORT_KEYS[sort], reverse=(direction == "desc"))

    def _sort_url(col: str) -> str:
        new_dir = "desc" if (sort == col and direction == "asc") else "asc"
        return f"?sort={col}&dir={new_dir}"

    def _sort_arrow(col: str) -> str:
        if sort != col:
            return "⇅"
        return "▲" if direction == "asc" else "▼"

    columns = [
        {"key": "titulo",      "label": "Título"},
        {"key": "mencoes",     "label": "Menções"},
        {"key": "ano",         "label": "Ano"},
        {"key": "modificacao", "label": "Última modificação"},
    ]
    for col in columns:
        col["url"] = _sort_url(col["key"])
        col["arrow"] = _sort_arrow(col["key"])
        col["active"] = sort == col["key"]

    return render(
        request,
        "curador/artigos_lista.html",
        {
            "nav_active": "artigos",
            "artigos": artigos,
            "columns": columns,
            "sort": sort,
            "direction": direction,
            "total": len(artigos),
        },
    )


@curador_or_admin_required
def artigo_detalhe(request, artigo_id: str):
    try:
        artigo = fetch_artigo_admin(artigo_id)
    except ApiError:
        raise Http404("Artigo não encontrado")

    for v in artigo.get("vinculos") or []:
        v["tipo_mencao_label"] = _TIPO_MENCAO_LABELS.get(v.get("tipo_mencao") or "", v.get("tipo_mencao") or "")

    excluir_url = reverse("excluir-artigo", kwargs={"artigo_id": artigo_id})

    return render(
        request,
        "curador/artigo_detalhe.html",
        {
            "nav_active": "artigos",
            "artigo": _namespace(artigo),
            "vinculos": [_namespace(v) for v in (artigo.get("vinculos") or [])],
            "total_vinculos": artigo.get("total_vinculos") or 0,
            "excluir_url": excluir_url,
        },
    )


@curador_or_admin_required
@require_POST
def excluir_artigo_view(request, artigo_id: str):
    try:
        excluir_artigo_admin(artigo_id)
        messages.success(request, "Artigo excluído com sucesso.")
    except ApiError as exc:
        messages.error(request, f"Não foi possível excluir o artigo: {exc}")
    return redirect("artigos-lista")


# ─────────────────────────────────────────────────────────────────────────────
# Usuários (admin only)
# ─────────────────────────────────────────────────────────────────────────────


@admin_required
def lista_usuarios(request):
    q = request.GET.get("q", "").strip()
    perfil = request.GET.get("perfil", "").strip()
    page = max(1, int(request.GET.get("page", 1) or 1))

    try:
        usuarios, meta = list_users(q=q or None, perfil=perfil or None, page=page)
    except ApiError as exc:
        messages.error(request, exc.message or "Erro ao carregar usuários.")
        usuarios, meta = [], {"total": 0, "page": 1, "pages": 1, "per_page": 20}

    return render(
        request,
        "curador/usuarios_lista.html",
        {
            "active_section": "usuarios",
            "usuarios": [_namespace(u) for u in usuarios],
            "meta": meta,
            "current_filters": {"q": q, "perfil": perfil},
            "perfis": ["coletor", "curador"],
        },
    )


@admin_required
@require_POST
def atualizar_perfil_usuario(request, user_id: str):
    perfil = (request.POST.get("perfil") or "").strip()
    try:
        update_user_perfil(user_id, perfil)
        messages.success(request, "Perfil atualizado com sucesso.")
    except ApiError as exc:
        messages.error(request, exc.message or "Erro ao atualizar perfil.")
    return redirect(reverse("usuarios-lista"))
