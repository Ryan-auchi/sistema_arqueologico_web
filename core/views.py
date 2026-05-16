from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from api_client.client import ApiError, clear_api_auth_token, fetch_all_bens_materiais, login_to_api, set_api_auth_token


def home(request):
    set_api_auth_token(request.session.get("api_auth_token", ""))

    try:
        sites = fetch_all_bens_materiais()
        state_count = len({site.get("uf") for site in sites if site.get("uf")})
    except ApiError:
        sites = ()
        state_count = 0

    return render(
        request,
        "core/home.html",
        {
            "nav_active": "home",
            "site_count": len(sites),
            "state_count": state_count,
        },
    )


def _safe_redirect_target(request, fallback_name="home"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return fallback_name


def auth_login(request):
    if request.method != "POST":
        return redirect("home")

    email = (request.POST.get("email") or "").strip()
    password = request.POST.get("password") or ""

    try:
        api_token, api_user = login_to_api(email, password)
    except ApiError as exc:
        messages.error(request, "Credenciais inválidas.") if getattr(exc, "status_code", None) == 401 else messages.error(request, "Nao foi possivel autenticar na API.")
        return redirect(_safe_redirect_target(request))

    UserModel = get_user_model()
    user, created = UserModel.objects.get_or_create(
        email=_normalize_email(email),
        defaults={
            "nome": api_user.get("name") or email,
            "perfil": api_user.get("perfil") or UserModel.PerfilUsuario.COLETOR,
            "classificacao": api_user.get("classificacao") or None,
            "ativo": True,
            "is_staff": api_user.get("perfil") in {"admin", "curador"},
        },
    )

    if not created:
        user.nome = api_user.get("name") or user.nome or email
        user.perfil = api_user.get("perfil") or user.perfil
        user.classificacao = api_user.get("classificacao") or user.classificacao
        user.ativo = True
        user.is_staff = user.perfil in {"admin", "curador"}
        user.save(update_fields=["nome", "perfil", "classificacao", "ativo", "is_staff"])

    request.session["api_auth_token"] = api_token
    set_api_auth_token(api_token)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Login efetuado com sucesso.")
    return redirect(_safe_redirect_target(request))


def auth_logout(request):
    if request.method == "POST":
        request.session.pop("api_auth_token", None)
        clear_api_auth_token()
        logout(request)
        messages.info(request, "Você saiu da sessão.")

    return redirect(_safe_redirect_target(request))


def auth_recovery_placeholder(request):
    if request.method == "POST":
        messages.info(request, "Recuperação de senha será implementada em breve.")

    return redirect(_safe_redirect_target(request))


def _normalize_email(email: str) -> str:
    return email.strip().lower()
