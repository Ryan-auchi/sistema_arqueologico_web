import json
from types import SimpleNamespace

from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_datetime

from api_client.client import (
    ApiError,
    fetch_all_bens_materiais,
    fetch_auditorias_for_bem,
    fetch_bem_material,
    invalidate_bens_cache,
    normalize_bem_material,
    toggle_publicado_bem_material,
)

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
    site, *, query="", state="", municipality="", conservation="", legal_level="", nature="", site_type=""
):
    search_target = " ".join(
        [
            str(site.name or ""),
            str(site.code or ""),
            str(site.municipality or ""),
            str(site.summary or ""),
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

    return True


def _filtered_sites(request):
    params = request.GET
    query = params.get("q", "").strip()
    state = params.get("state", "").strip()
    municipality = params.get("municipality", "").strip()
    conservation = params.get("conservation", "").strip()
    legal_level = params.get("legal_level", "").strip()
    nature = params.get("nature", "").strip()
    site_type = params.get("type", "").strip()

    try:
        sites = [_site_payload(site) for site in fetch_all_bens_materiais()]
    except ApiError:
        sites = []

    filtered = [
        site
        for site in sites
        if _site_filter(
            site,
            query=query,
            state=state,
            municipality=municipality,
            conservation=conservation,
            legal_level=legal_level,
            nature=nature,
            site_type=site_type,
        )
    ]

    return filtered, {
        "conservation": conservation,
        "legal_level": legal_level,
        "nature": nature,
        "state": state,
        "municipality": municipality,
        "type": site_type,
        "q": query,
    }


def _filter_options(sites):
    states = sorted({site.state for site in sites if site.state})
    municipalities = sorted({site.municipality for site in sites if site.municipality})
    natures = sorted({site.raw.get("natureza") for site in sites if site.raw.get("natureza")})
    types = sorted({site.raw.get("tipo") for site in sites if site.raw.get("tipo")})

    municipality_options = [("", "Todos os municípios")] + [(value, value.title()) for value in municipalities]
    nature_options = [(value, value.title()) for value in natures]
    type_options = [(value, value.title()) for value in types]

    return states, municipality_options, [], [], nature_options, type_options


def pesquisa_mapa(request):
    sites, current_filters = _filtered_sites(request)
    state_options, municipality_options, conservation_options, legal_level_options, nature_options, type_options = (
        _filter_options(sites)
    )

    return render(
        request,
        "pesquisa/pesquisa_mapa.html",
        {
            "nav_active": "mapa",
            "sites": sites,
            "sites_json_url": "/api/sitios/",
            "conservation_options": conservation_options,
            "municipality_options": municipality_options,
            "legal_level_options": legal_level_options,
            "nature_options": nature_options,
            "type_options": type_options,
            "state_options": state_options,
            "current_filters": current_filters,
        },
    )


def pesquisa_lista(request):
    sites, current_filters = _filtered_sites(request)
    paginator = Paginator(sites, 6)
    page_obj = paginator.get_page(request.GET.get("page"))

    state_options, municipality_options, conservation_options, legal_level_options, nature_options, type_options = (
        _filter_options(sites)
    )

    return render(
        request,
        "pesquisa/pesquisa_lista.html",
        {
            "nav_active": "lista",
            "page_obj": page_obj,
            "paginator_count": paginator.count,
            "conservation_options": conservation_options,
            "municipality_options": municipality_options,
            "legal_level_options": legal_level_options,
            "nature_options": nature_options,
            "type_options": type_options,
            "state_options": state_options,
            "current_filters": current_filters,
        },
    )


def site_detail(request, sitio_id):
    try:
        current_site = _site_payload(fetch_bem_material(sitio_id))
    except ApiError:
        raise Http404("Sítio não encontrado")

    if request.method == "POST" and request.POST.get("action") == "toggle_publicado":
        publish_selected = request.POST.get("published_selected") == "1"
        try:
            updated_site = toggle_publicado_bem_material(sitio_id, publish_selected)
            current_site = _site_payload(updated_site)
            invalidate_bens_cache()
        except ApiError:
            raise Http404("Não foi possível atualizar o sítio")

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
        },
    )


def api_sites(request):
    sites, current_filters = _filtered_sites(request)

    return JsonResponse(
        {
            "count": len(sites),
            "results": [_site_payload_to_dict(site) for site in sites],
            "filters": current_filters,
        }
    )
