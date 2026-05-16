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
from functools import wraps
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_datetime

from api_client.client import (
    ApiError,
    fetch_all_curadorias,
    fetch_auditoria,
    fetch_curadoria,
    invalidate_bens_cache,
    list_auditorias,
    normalize_bem_material,
    update_curadoria_avaliacao,
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
    }
    return labels.get(field_name, field_name.replace("_", " ").title())


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
    coleta = raw.get("coleta") or {}
    bem_material = raw.get("bem_material") or {}
    usuario = _normalize_user(raw.get("usuario") or {})
    curador = _normalize_user(raw.get("curador") or {})

    display_user = curador or usuario or {"nome": "Equipe de curadoria"}

    iphan = bem_material.get("codigo_iphan") or coleta.get("codigo_iphan") or "IPHAN não informado"
    nome = coleta.get("nome_bem") or bem_material.get("nome_bem") or "Sem nome informado"
    status_display = _status_label(raw.get("status"))

    return _namespace(
        {
            "id": raw.get("id"),
            "codigo_iphan_display": iphan,
            "nome_display": nome,
            "observacao": raw.get("observacao") or "",
            "criado_em": _to_datetime(raw.get("created_at") or raw.get("data_avaliacao")),
            "status": raw.get("status") or "pendente",
            "acao_resultante": raw.get("acao_resultante") or "",
            "bem_material_id": raw.get("bem_material_id"),
            "usuario": display_user,
            "coleta": coleta,
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
_AUDIT_ALWAYS_SHOW = {"nome_bem", "natureza", "tipo", "publicado"}

# Ordem preferencial de exibição dos campos na tabela de auditoria.
_AUDIT_FIELD_ORDER = [
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
]


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

    A API já filtra por pendente em GET /admin/curadorias.
    O filtro local de query é apenas para busca no conjunto retornado.
    """
    query = request.GET.get("q", "").strip().lower()

    try:
        # fetch_all_curadorias já pagina a API e retorna todos os registros.
        curadorias = [
            _curadoria_item(item)
            for item in fetch_all_curadorias()
            if str(item.get("status") or "").lower() == "pendente"
        ]
    except ApiError:
        curadorias = []
        messages.warning(request, "Não foi possível carregar as curadorias da API.")

    if query:
        curadorias = [
            c
            for c in curadorias
            if query in str(c.codigo_iphan_display).lower()
            or query in str(c.nome_display).lower()
            or query in str(c.observacao).lower()
        ]

    paginator = Paginator(curadorias, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "curador/curadoria_fila.html",
        {
            "nav_active": "curadoria",
            "page_obj": page_obj,
            "query": request.GET.get("q", "").strip(),
            "total_pendentes": len(curadorias),
            "conflitos": len([c for c in curadorias if c.observacao]),
        },
    )


@curador_or_admin_required
def curadoria_revisao(request, curadoria_id):
    """
    Exibe o split-screen de revisão de uma curadoria e processa a decisão.

    GET  — exibe comparação entre os dados da coleta e o bem_material oficial.
    POST — envia a avaliação para PATCH /admin/curadorias/{id}/avaliar.

    Enum values esperados pela API (camelCase):
      acao_resultante: criarSitio | atualizarSitio | rejeitar
      status:          aprovado   | rejeitado
    """
    try:
        curadoria_raw = fetch_curadoria(curadoria_id)
    except ApiError:
        raise Http404("Curadoria não encontrada")

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "rejeitar":
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

                # Campos selecionados individualmente pelo curador no template.
                # selected_fields é um JSON array de nomes de campos (ex.: ["nome_bem","municipio"]).
                try:
                    selected_field_names = json.loads(request.POST.get("selected_fields", "[]"))
                    if not isinstance(selected_field_names, list):
                        selected_field_names = []
                except (ValueError, TypeError):
                    selected_field_names = []

                incoming = _incoming_data(curadoria_raw)

                _all_fields = [
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
                    "ano_registro",
                    "descricao_atualizacao",
                ]

                if selected_field_names:
                    # Apenas os campos que o curador aceitou explicitamente.
                    campos = {
                        f: incoming.get(f)
                        for f in selected_field_names
                        if f in incoming and incoming.get(f) not in (None, "", [])
                    }
                else:
                    # Nenhum campo específico selecionado → aplica todos não-vazios.
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
            "requires_iphan_form": not official_record_exists,
        },
    )


@curador_or_admin_required
def audit_logs(request):
    """
    Lista paginada de auditorias via GET /admin/auditorias.

    A API retorna 50 registros por página ordenados por data_hora DESC.
    A paginação aqui segue exatamente a paginação da API.
    """
    query = request.GET.get("q", "").strip().lower()
    page = max(1, int(request.GET.get("page", 1) or 1))

    try:
        items, meta = list_auditorias(page=page)
    except ApiError:
        items, meta = [], {"total": 0, "page": 1, "pages": 1, "per_page": 50}

    entries = []
    for item in items:
        user = _normalize_user(item.get("usuario") or {})
        op = item.get("operacao") or ""
        before = item.get("valor_anterior") or {}
        after = item.get("valor_novo") or {}

        entries.append(
            {
                "audit_id": item.get("id"),
                "created_at": _to_datetime(item.get("data_hora") or item.get("created_at")),
                "user_name": user.get("nome") or user.get("name") or user.get("email") or "Sistema",
                "operation": op,
                "operation_label": op.replace("_", " ").upper() or "ATUALIZAR",
                "operation_class": _op_class(op),
                "entity": item.get("entidade_tipo"),
                "target": (
                    f"{item.get('entidade_tipo')} #{item.get('entidade_id')}"
                    if item.get("entidade_id")
                    else item.get("entidade_tipo")
                ),
                "before": before,
                "after": after,
                "before_preview": _truncate(json.dumps(before, ensure_ascii=False)),
                "after_preview": _truncate(json.dumps(after, ensure_ascii=False)),
            }
        )

    # Filtro local por query (busca no conjunto retornado pela API).
    if query:
        entries = [
            e
            for e in entries
            if query in str(e["user_name"]).lower()
            or query in str(e["operation_label"]).lower()
            or query in str(e["entity"]).lower()
            or query in str(e["target"]).lower()
        ]

    # Paginação reflete exatamente o que a API retornou.
    paginator = Paginator(entries, meta.get("per_page", 50))
    page_obj = paginator.get_page(meta.get("page", 1))

    return render(
        request,
        "curador/audit_logs.html",
        {
            "nav_active": "audit",
            "page_obj": page_obj,
            "query": request.GET.get("q", "").strip(),
            "total_logs": meta.get("total", len(entries)),
            "sync_status": "NOMINAL",
            "total_users": len({e["user_name"] for e in entries}),
            # Paginação da API (para os links anterior/próximo no template).
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
    if raw.get("curadoria_id"):
        try:
            curadoria_raw = fetch_curadoria(raw["curadoria_id"])
            audit_ns.curadoria = _namespace(
                {
                    "observacao": curadoria_raw.get("observacao") or "",
                    "status": curadoria_raw.get("status") or "",
                }
            )
        except ApiError:
            audit_ns.curadoria = _namespace({"observacao": "", "status": ""})

    comparisons = _field_comparisons_from_audit(audit_ns)

    return render(
        request,
        "curador/audit_detail.html",
        {
            "nav_active": "audit",
            "audit_entry": audit_ns,
            "comparisons": comparisons,
            "audit_id": raw.get("id"),
        },
    )
