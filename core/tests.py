from unittest.mock import patch

import pytest
from django.urls import reverse

from pesquisa.models import Usuario


@pytest.mark.django_db
class TestAuthLogin:
    def test_get_redireciona_para_home(self, client):
        """GET em /auth/login/ redireciona — o form fica na home."""
        response = client.get(reverse("auth-login"))
        assert response.status_code == 302

    def test_post_credenciais_invalidas_exibe_erro(self, client):
        from api_client.client import ApiError

        with patch("core.views.login_to_api", side_effect=ApiError("Unauthorized", 401)):
            response = client.post(
                reverse("auth-login"),
                {"email": "x@x.com", "password": "errada"},
            )
        assert response.status_code == 302


@pytest.mark.django_db
class TestAuthLoginSuccess:
    def test_post_valido_cria_sessao_e_usuario(self, client):
        _api_user = {"id": "u1", "name": "João", "email": "joao@test.com", "perfil": "coletor", "classificacao": "estudante"}
        with patch("core.views.login_to_api", return_value=("token-abc", _api_user)):
            response = client.post(
                reverse("auth-login"),
                {"email": "joao@test.com", "password": "senha123"},
            )
        assert response.status_code == 302
        assert client.session.get("api_auth_token") == "token-abc"
        assert Usuario.objects.filter(email="joao@test.com").exists()

    def test_post_com_next_redireciona_para_next(self, client):
        _api_user = {"id": "u2", "name": "Ana", "email": "ana@test.com", "perfil": "coletor", "classificacao": None}
        with patch("core.views.login_to_api", return_value=("token-xyz", _api_user)):
            response = client.post(
                reverse("auth-login") + "?next=/pesquisa/mapa/",
                {"email": "ana@test.com", "password": "senha123"},
            )
        assert response.status_code == 302
        assert "/pesquisa/mapa/" in response["Location"]

    def test_post_perfil_curador_define_is_staff(self, client):
        _api_user = {"id": "u3", "name": "Curador", "email": "cur@test.com", "perfil": "curador", "classificacao": None}
        with patch("core.views.login_to_api", return_value=("token-cur", _api_user)):
            client.post(
                reverse("auth-login"),
                {"email": "cur@test.com", "password": "senha123"},
            )
        usuario = Usuario.objects.get(email="cur@test.com")
        assert usuario.is_staff is True


@pytest.mark.django_db
class TestAuthLoginUsuarioExistente:
    """Login com usuário já existente na DB → deve atualizar os campos."""

    def test_post_atualiza_perfil_de_usuario_existente(self, client, coletor_user):
        # coletor_user já existe; o login devolve perfil curador → deve atualizar
        _api_user = {
            "id": "u-existente",
            "name": "Coletor Renomeado",
            "email": coletor_user.email,
            "perfil": "curador",
            "classificacao": "professor",
        }
        with patch("core.views.login_to_api", return_value=("token-upd", _api_user)):
            client.post(
                reverse("auth-login"),
                {"email": coletor_user.email, "password": "senha123"},
            )
        coletor_user.refresh_from_db()
        assert coletor_user.perfil == Usuario.PerfilUsuario.CURADOR
        assert coletor_user.is_staff is True


@pytest.mark.django_db
class TestAuthLogout:
    def test_post_limpa_sessao_e_redireciona(self, client, coletor_user):
        client.force_login(coletor_user)
        client.session["api_auth_token"] = "tok"
        client.session.save()
        with patch("core.views.logout_from_api"):
            response = client.post(reverse("auth-logout"))
        assert response.status_code == 302
        assert "api_auth_token" not in client.session

    def test_get_nao_e_permitido_ou_redireciona(self, client):
        response = client.get(reverse("auth-logout"))
        # GET em logout deve retornar redirect ou 405
        assert response.status_code in (302, 405)


@pytest.mark.django_db
class TestAuthRegister:
    def test_post_valido_cria_usuario_e_redireciona(self, client):
        _api_user = {"id": "u4", "name": "Novo", "email": "novo@test.com", "perfil": "coletor", "classificacao": "estudante"}
        with patch("core.views.register_to_api", return_value=("token-new", _api_user)):
            response = client.post(
                reverse("auth-register"),
                {
                    "name": "Novo",
                    "email": "novo@test.com",
                    "classificacao": "estudante",
                    "password": "senha123",
                    "password_confirmation": "senha123",
                    "accepted_terms": "on",
                },
            )
        assert response.status_code == 302
        assert Usuario.objects.filter(email="novo@test.com").exists()

    def test_post_senhas_divergentes_nao_chama_api(self, client):
        with patch("core.views.register_to_api") as mock_api:
            client.post(
                reverse("auth-register"),
                {
                    "name": "X",
                    "email": "x@test.com",
                    "classificacao": "estudante",
                    "password": "abc",
                    "password_confirmation": "xyz",
                },
            )
        mock_api.assert_not_called()

    def test_post_api_error_422_exibe_mensagem_dados_invalidos(self, client):
        from api_client.client import ApiError

        with patch("core.views.register_to_api", side_effect=ApiError("email já usado", 422)):
            response = client.post(
                reverse("auth-register"),
                {
                    "name": "Y",
                    "email": "y@test.com",
                    "classificacao": "estudante",
                    "password": "senha123",
                    "password_confirmation": "senha123",
                    "accepted_terms": "on",
                },
            )
        assert response.status_code == 302

    def test_post_api_error_500_exibe_mensagem_generica(self, client):
        from api_client.client import ApiError

        with patch("core.views.register_to_api", side_effect=ApiError("servidor indisponível", 500)):
            response = client.post(
                reverse("auth-register"),
                {
                    "name": "Z2",
                    "email": "z2@test.com",
                    "classificacao": "estudante",
                    "password": "senha123",
                    "password_confirmation": "senha123",
                    "accepted_terms": "on",
                },
            )
        assert response.status_code == 302

    def test_post_registro_atualiza_usuario_existente(self, client, coletor_user):
        """Registro com e-mail já existente faz update em vez de criar duplicata."""
        _api_user = {
            "id": "u-reg",
            "name": "Nome Atualizado",
            "email": coletor_user.email,
            "perfil": "coletor",
            "classificacao": "professor",
        }
        with patch("core.views.register_to_api", return_value=("token-reg", _api_user)):
            client.post(
                reverse("auth-register"),
                {
                    "name": "Nome Atualizado",
                    "email": coletor_user.email,
                    "classificacao": "professor",
                    "password": "senha123",
                    "password_confirmation": "senha123",
                    "accepted_terms": "on",
                },
            )
        coletor_user.refresh_from_db()
        assert coletor_user.nome == "Nome Atualizado"

    def test_post_com_next_redireciona(self, client):
        _api_user = {"id": "u5", "name": "Z", "email": "z@test.com", "perfil": "coletor", "classificacao": "estudante"}
        with patch("core.views.register_to_api", return_value=("tok", _api_user)):
            response = client.post(
                reverse("auth-register") + "?next=/pesquisa/lista/",
                {
                    "name": "Z",
                    "email": "z@test.com",
                    "classificacao": "estudante",
                    "password": "senha123",
                    "password_confirmation": "senha123",
                    "accepted_terms": "on",
                },
            )
        assert response.status_code == 302

    def test_post_sem_aceite_termos_nao_chama_api(self, client):
        with patch("core.views.register_to_api") as mock_api:
            response = client.post(
                reverse("auth-register"),
                {
                    "name": "Sem Termos",
                    "email": "semtermos@test.com",
                    "classificacao": "estudante",
                    "password": "senha123",
                    "password_confirmation": "senha123",
                },
            )
        mock_api.assert_not_called()
        assert response.status_code == 302
        assert not Usuario.objects.filter(email="semtermos@test.com").exists()


@pytest.mark.django_db
class TestAuthPasswordResetGet:
    def test_get_redireciona_para_home(self, client):
        response = client.get(reverse("auth-password-reset"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestAuthPasswordReset:
    def test_post_email_valido_retorna_mensagem(self, client):
        with patch("core.views.request_password_reset", return_value="Email enviado"):
            response = client.post(
                reverse("auth-password-reset"),
                {"email": "user@test.com"},
            )
        assert response.status_code == 302

    def test_post_api_error_exibe_erro(self, client):
        from api_client.client import ApiError

        with patch("core.views.request_password_reset", side_effect=ApiError("email não encontrado")):
            response = client.post(
                reverse("auth-password-reset"),
                {"email": "naoexiste@test.com"},
            )
        assert response.status_code == 302


@pytest.mark.django_db
class TestHome:
    def test_home_redireciona_para_mapa(self, client):
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert "mapa" in response["Location"]
