import json
import logging
from types import SimpleNamespace

from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_datetime

from api_client.client import (
    ApiError,
    atualizar_curador_responsavel,
    buscar_artigo_por_doi,
    excluir_bem_material,
    fetch_all_bens_materiais,
    fetch_artigos_por_bem,
    fetch_auditorias_for_bem,
    fetch_bem_material,
    fetch_colaboradores_por_bem,
    fetch_curadores,
    invalidate_bens_cache,
    normalize_bem_material,
    remover_vinculo_artigo,
    set_api_auth_token,
    submeter_artigo,
    toggle_publicado_bem_material,
)

logger = logging.getLogger(__name__)

ENTITY_TYPE_BEM_MATERIAL = "App\\Models\\BemMaterial"


class RemoteRelationList(list):
    def all(self):
        return self


def _as_namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(
            **{key: inner_value if key == "raw" else _as_namespace(inner_value) for key, inner_value in value.items()}
        )
    if isinstance(value, RemoteRelationList):
        return RemoteRelationList([_as_namespace(item) for item in value])
    if isinstance(value, list):
        return [_as_namespace(item) for item in value]
    return value


def _as_datetime(value):
    if not value:
        return None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    parsed_value = parse_datetime(str(value))
    return parsed_value or value


def _site_payload(site):
    normalized = normalize_bem_material(site)
    latitude = normalized.get("latitude")
    longitude = normalized.get("longitude")
    nature = normalized.get("natureza") or "Não informado"
    midias = RemoteRelationList(
        [_as_namespace(media) for media in normalized.get("midias") or [] if isinstance(media, dict)]
    )
    responsavel = (
        _as_namespace(normalized.get("responsavel") or {}) if isinstance(normalized.get("responsavel"), dict) else {}
    )
    curador_responsavel = (
        _as_namespace(normalized.get("curador_responsavel") or {})
        if isinstance(normalized.get("curador_responsavel"), dict)
        else {}
    )

    payload = {
        "id": normalized.get("id"),
        "coleta_id": normalized.get("coleta_id"),
        "name": normalized.get("nome_bem"),
        "nome_bem": normalized.get("nome_bem"),
        "code": normalized.get("codigo_iphan"),
        "codigo_iphan": normalized.get("codigo_iphan"),
        "published": normalized.get("published", False),
        "publicado": normalized.get("publicado", False),
        "published_label": normalized.get("published_label", "Nao publicado"),
        "municipality": normalized.get("municipio") or "",
        "municipio": normalized.get("municipio") or "",
        "state": normalized.get("uf") or "",
        "uf": normalized.get("uf") or "",
        "conservation": (normalized.get("natureza") or "não informado").lower(),
        "natureza": normalized.get("natureza") or "",
        "badge": nature.title(),
        "period": normalized.get("tipo") or "",
        "tipo": normalized.get("tipo") or "",
        "nomes_populares": normalized.get("nomes_populares") or "",
        "meios_acesso": normalized.get("meios_acesso") or "",
        "artefatos": list(normalized.get("artefatos") or []),
        "summary": normalized.get("descricao_atualizacao") or "Sem resumo técnico.",
        "descricao_atualizacao": normalized.get("descricao_atualizacao") or "",
        "history": normalized.get("meios_acesso") or "Sem histórico consolidado.",
        "legal_protection": "Não informado",
        "utm": "Não informado",
        "latitude": latitude,
        "longitude": longitude,
        "cep": normalized.get("cep") or "",
        "endereco": normalized.get("endereco") or "",
        "geojson": normalized.get("geojson"),
        "geometry": normalized.get("geometry") or normalized.get("geojson"),
        "geometry_type": normalized.get("geometry_type") or "",
        "ano_registro": normalized.get("ano_registro"),
        "criado_em": _as_datetime(normalized.get("criado_em")),
        "atualizado_em": _as_datetime(normalized.get("atualizado_em")),
        "deletado_em": _as_datetime(normalized.get("deletado_em")),
        "midias": midias,
        "responsavel": responsavel,
        "curador_responsavel": curador_responsavel,
        "raw": normalized,
    }

    return _as_namespace(payload)


def _site_payload_to_dict(site):
    def to_plain(value):
        if isinstance(value, SimpleNamespace):
            return {key: to_plain(inner_value) for key, inner_value in vars(value).items()}
        if isinstance(value, list):
            return [to_plain(item) for item in value]
        if isinstance(value, dict):
            return {key: to_plain(inner_value) for key, inner_value in value.items()}
        return value

    return {
        "id": site.id,
        "name": site.name,
        "code": site.code,
        "published": site.published,
        "published_label": site.published_label,
        "municipality": site.municipality,
        "state": site.state,
        "conservation": site.conservation,
        "badge": site.badge,
        "period": site.period,
        "summary": site.summary,
        "history": site.history,
        "legal_protection": site.legal_protection,
        "utm": site.utm,
        "latitude": site.latitude,
        "longitude": site.longitude,
        "geometry": to_plain(site.geometry),
        "geometry_type": site.geometry_type,
    }


def _site_filter(
    site,
    *,
    query="",
    state="",
    municipality="",
    nature="",
    site_type="",
    artefato="",
    ano_min="",
    ano_max="",
    show_unpublished=False,
):
    if not show_unpublished and not site.publicado:
        return False

    artefatos_str = " ".join(str(a) for a in (site.artefatos or []))
    search_target = " ".join(
        [
            str(site.nome_bem or ""),
            str(site.codigo_iphan or ""),
            str(site.nomes_populares or ""),
            str(site.municipality or ""),
            str(site.descricao_atualizacao or ""),
            artefatos_str,
        ]
    ).lower()

    if query and query.lower() not in search_target:
        return False

    if state and str(site.state or "").lower() != state.lower():
        return False

    if municipality and str(site.municipality or "").lower() != municipality.lower():
        return False

    if nature and str(site.raw.get("natureza") or "").lower() != nature.lower():
        return False

    if site_type and str(site.raw.get("tipo") or "").lower() != site_type.lower():
        return False

    if artefato:
        artefatos = [str(a).lower() for a in (site.artefatos or [])]
        if artefato.lower() not in artefatos:
            return False

    ano = site.ano_registro
    if ano_min:
        try:
            if not ano or int(ano) < int(ano_min):
                return False
        except (ValueError, TypeError):
            pass

    if ano_max:
        try:
            if not ano or int(ano) > int(ano_max):
                return False
        except (ValueError, TypeError):
            pass

    return True


def _filtered_sites(request):
    params = request.GET
    query = params.get("q", "").strip()
    state = params.get("state", "").strip()
    municipality = params.get("municipality", "").strip()
    nature = params.get("nature", "").strip()
    site_type = params.get("type", "").strip()
    artefato = params.get("artefato", "").strip()
    ano_min = params.get("ano_min", "").strip()
    ano_max = params.get("ano_max", "").strip()
    show_unpublished = params.get("show_unpublished", "") == "1"

    try:
        all_sites = [_site_payload(site) for site in fetch_all_bens_materiais()]
    except ApiError:
        all_sites = []

    filtered = [
        site
        for site in all_sites
        if _site_filter(
            site,
            query=query,
            state=state,
            municipality=municipality,
            nature=nature,
            site_type=site_type,
            artefato=artefato,
            ano_min=ano_min,
            ano_max=ano_max,
            show_unpublished=show_unpublished,
        )
    ]

    return filtered, all_sites, {
        "nature": nature,
        "state": state,
        "municipality": municipality,
        "type": site_type,
        "artefato": artefato,
        "ano_min": ano_min,
        "ano_max": ano_max,
        "show_unpublished": "1" if show_unpublished else "",
        "q": query,
    }


def _filter_options(all_sites):
    states = sorted({site.state for site in all_sites if site.state})
    municipalities = sorted({site.municipality for site in all_sites if site.municipality})
    natures = sorted({site.raw.get("natureza") for site in all_sites if site.raw.get("natureza")})
    types = sorted({site.raw.get("tipo") for site in all_sites if site.raw.get("tipo")})

    artefatos: set[str] = set()
    for site in all_sites:
        for a in site.artefatos or []:
            if a:
                artefatos.add(str(a))

    municipality_options = [("", "Todos os municípios")] + [(v, v.title()) for v in municipalities]
    nature_options = [(v, v.title()) for v in natures]
    type_options = [(v, v.title()) for v in types]
    artefato_options = [(v, v.title()) for v in sorted(artefatos)]

    return states, municipality_options, nature_options, type_options, artefato_options


def pesquisa_mapa(request):
    set_api_auth_token(request.session.get("api_auth_token", ""))
    sites, all_sites, current_filters = _filtered_sites(request)
    state_options, municipality_options, nature_options, type_options, artefato_options = _filter_options(all_sites)

    return render(
        request,
        "pesquisa/pesquisa_mapa.html",
        {
            "nav_active": "mapa",
            "sites": sites,
            "sites_json_url": "/api/sitios/",
            "municipality_options": municipality_options,
            "nature_options": nature_options,
            "type_options": type_options,
            "artefato_options": artefato_options,
            "state_options": state_options,
            "current_filters": current_filters,
        },
    )


def pesquisa_lista(request):
    set_api_auth_token(request.session.get("api_auth_token", ""))
    sites, all_sites, current_filters = _filtered_sites(request)
    paginator = Paginator(sites, 6)
    page_obj = paginator.get_page(request.GET.get("page"))
    state_options, municipality_options, nature_options, type_options, artefato_options = _filter_options(all_sites)

    filter_qs = "&".join(
        f"{k}={v}" for k, v in current_filters.items() if v
    )

    return render(
        request,
        "pesquisa/pesquisa_lista.html",
        {
            "nav_active": "lista",
            "page_obj": page_obj,
            "paginator_count": paginator.count,
            "municipality_options": municipality_options,
            "nature_options": nature_options,
            "type_options": type_options,
            "artefato_options": artefato_options,
            "state_options": state_options,
            "current_filters": current_filters,
            "filter_qs": filter_qs,
        },
    )


def site_detail(request, sitio_id):
    set_api_auth_token(request.session.get("api_auth_token", ""))
    try:
        current_site = _site_payload(fetch_bem_material(sitio_id))
    except ApiError:
        raise Http404("Sítio não encontrado")

    is_curador_or_admin = (
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or getattr(request.user, "perfil", None) in ("admin", "curador")
        )
    )

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "toggle_publicado":
            publish_selected = request.POST.get("published_selected") == "1"
            try:
                updated_site = toggle_publicado_bem_material(sitio_id, publish_selected)
                current_site = _site_payload(updated_site)
                invalidate_bens_cache()
            except ApiError:
                raise Http404("Não foi possível atualizar o sítio")
            return redirect("pesquisa-detalhe", sitio_id=sitio_id)

        elif action == "submeter_artigo":
            payload: dict = {
                "bem_material_id": sitio_id,
                "doi": request.POST.get("doi") or None,
                "titulo": request.POST.get("titulo") or None,
                "autores": request.POST.get("autores") or None,
                "ano_publicacao": request.POST.get("ano_publicacao") or None,
                "periodico": request.POST.get("periodico") or None,
                "idioma": request.POST.get("idioma") or "pt",
                "resumo": request.POST.get("resumo") or None,
                "link_acesso": request.POST.get("link_acesso") or None,
                "tipo_mencao": request.POST.get("tipo_mencao") or None,
                "trecho_relevante": request.POST.get("trecho_relevante") or None,
            }
            # Se o artigo já existe na base, inclui o artigo_id para que a API
            # faça o Cenário A (apenas cria o vínculo ArtigoBemMaterial).
            artigo_id = request.POST.get("artigo_id")
            if artigo_id:
                payload["artigo_id"] = artigo_id
            try:
                submeter_artigo(payload)
                from django.contrib import messages as _messages
                _messages.success(request, "Sugestão enviada para curadoria.")
            except ApiError as exc:
                from django.contrib import messages as _messages
                _messages.error(request, f"Não foi possível enviar a sugestão: {exc}")
            return redirect("pesquisa-detalhe", sitio_id=sitio_id)

        elif action == "remover_vinculo":
            vinculo_id = request.POST.get("vinculo_id", "")
            try:
                remover_vinculo_artigo(vinculo_id)
                from django.contrib import messages as _messages
                _messages.success(request, "Vínculo removido com sucesso.")
            except ApiError as exc:
                from django.contrib import messages as _messages
                _messages.error(request, f"Não foi possível remover o vínculo: {exc}")
            return redirect("pesquisa-detalhe", sitio_id=sitio_id)

        elif action == "atualizar_curador_responsavel":
            if not is_curador_or_admin:
                raise Http404
            curador_id = request.POST.get("curador_responsavel_id") or None
            try:
                updated_site = atualizar_curador_responsavel(sitio_id, curador_id)
                current_site = _site_payload(updated_site)
                from django.contrib import messages as _messages
                _messages.success(request, "Curador responsável atualizado com sucesso.")
            except ApiError as exc:
                from django.contrib import messages as _messages
                _messages.error(request, f"Não foi possível atualizar o curador responsável: {exc}")
            return redirect("pesquisa-detalhe", sitio_id=sitio_id)

        elif action == "excluir_bem":
            if not is_curador_or_admin:
                raise Http404
            try:
                excluir_bem_material(sitio_id)
                invalidate_bens_cache()
                from django.contrib import messages as _messages
                _messages.success(request, "Bem material excluído com sucesso.")
                return redirect("pesquisa-lista")
            except ApiError as exc:
                from django.contrib import messages as _messages
                _messages.error(request, f"Não foi possível excluir o bem material: {exc}")
                return redirect("pesquisa-detalhe", sitio_id=sitio_id)

    first_image = None
    for media_item in current_site.midias.all():
        if getattr(media_item, "tipo", "") == "imagem" and getattr(media_item, "url", ""):
            first_image = media_item
            break

    hero_image_url = getattr(first_image, "url", "") if first_image else ""

    try:
        audit_entries = [
            _as_namespace(entry)
            for entry in fetch_auditorias_for_bem(current_site.id, entidade_tipo=ENTITY_TYPE_BEM_MATERIAL)
        ]
    except ApiError:
        audit_entries = []

    try:
        artigos = fetch_artigos_por_bem(sitio_id)
    except ApiError:
        artigos = []

    colaboradores: list = []
    colaboradores_erro: str = ""
    try:
        colaboradores = fetch_colaboradores_por_bem(sitio_id)
    except ApiError as _colabs_exc:
        logger.warning(
            "colaboradores: API error for bem=%s — %s (HTTP %s)",
            sitio_id,
            _colabs_exc.message,
            _colabs_exc.status_code,
        )
        colaboradores_erro = f"HTTP {_colabs_exc.status_code}: {_colabs_exc.message}"

    curadores_list: list = []
    if is_curador_or_admin:
        try:
            curadores_list = fetch_curadores()
        except ApiError:
            pass

    site_geometry_geojson = ""
    if current_site.geometry:
        site_geometry_geojson = (
            json.dumps(current_site.geometry, ensure_ascii=False)
            if isinstance(current_site.geometry, dict)
            else str(current_site.geometry)
        )

    return render(
        request,
        "pesquisa/pesquisa_detail.html",
        {
            "nav_active": "detalhe",
            "sitio": current_site,
            "hero_image_url": hero_image_url,
            "audit_entries": audit_entries,
            "site_geometry_geojson": site_geometry_geojson,
            "artigos": artigos,
            "colaboradores": colaboradores,
            "colaboradores_erro": colaboradores_erro,
            "is_curador_or_admin": is_curador_or_admin,
            "curadores_list": curadores_list,
        },
    )


def api_buscar_doi(request):
    """AJAX — busca artigo por DOI na base: GET /api/artigo-doi/?doi=..."""
    doi = request.GET.get("doi", "").strip()
    if not doi:
        return JsonResponse({"artigo": None})
    artigo = buscar_artigo_por_doi(doi)
    return JsonResponse({"artigo": artigo})


def api_sites(request):
    sites, _all, current_filters = _filtered_sites(request)

    return JsonResponse(
        {
            "count": len(sites),
            "results": [_site_payload_to_dict(site) for site in sites],
            "filters": current_filters,
        }
    )
