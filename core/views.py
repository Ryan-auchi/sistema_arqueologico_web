from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from api_client.client import (
    ApiError,
    clear_api_auth_token,
    fetch_all_bens_materiais,
    login_to_api,
    register_to_api,
    request_password_reset,
    set_api_auth_token,
)


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
        messages.error(request, "Credenciais inválidas.") if getattr(
            exc, "status_code", None
        ) == 401 else messages.error(request, "Nao foi possivel autenticar na API.")
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


def auth_register(request):
    if request.method != "POST":
        return redirect("home")

    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    password = request.POST.get("password") or ""
    password_confirmation = request.POST.get("password_confirmation") or ""
    classificacao = (request.POST.get("classificacao") or "").strip()

    if password != password_confirmation:
        messages.error(request, "As senhas não coincidem.")
        return redirect(_safe_redirect_target(request))

    try:
        api_token, api_user = register_to_api(name, email, password, password_confirmation, classificacao)
    except ApiError as exc:
        status = getattr(exc, "status_code", None)
        if status == 422:
            messages.error(request, "Dados inválidos. Verifique os campos e tente novamente.")
        else:
            messages.error(request, exc.message or "Não foi possível criar a conta.")
        return redirect(_safe_redirect_target(request))

    UserModel = get_user_model()
    user, created = UserModel.objects.get_or_create(
        email=_normalize_email(email),
        defaults={
            "nome": api_user.get("name") or name,
            "perfil": api_user.get("perfil") or UserModel.PerfilUsuario.COLETOR,
            "classificacao": api_user.get("classificacao") or classificacao or None,
            "ativo": True,
            "is_staff": False,
        },
    )

    if not created:
        user.nome = api_user.get("name") or user.nome or name
        user.perfil = api_user.get("perfil") or user.perfil
        user.classificacao = api_user.get("classificacao") or user.classificacao
        user.ativo = True
        user.save(update_fields=["nome", "perfil", "classificacao", "ativo"])

    request.session["api_auth_token"] = api_token
    set_api_auth_token(api_token)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, f"Conta criada com sucesso. Bem-vindo, {user.nome or email}!")
    return redirect(_safe_redirect_target(request))


def auth_password_reset(request):
    if request.method != "POST":
        return redirect("home")

    email = (request.POST.get("email") or "").strip()

    try:
        msg = request_password_reset(email)
    except ApiError as exc:
        messages.error(request, exc.message or "Não foi possível processar a solicitação.")
        return redirect(_safe_redirect_target(request))

    messages.info(request, msg or "Se este e-mail estiver cadastrado, você receberá as instruções em breve.")
    return redirect(_safe_redirect_target(request))


def _normalize_email(email: str) -> str:
    return email.strip().lower()
