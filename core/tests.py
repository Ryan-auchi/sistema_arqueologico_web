from unittest.mock import patch

import pytest
from django.urls import reverse


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
class TestHome:
    def test_home_carrega_sem_api(self, client):
        """Home deve renderizar mesmo quando a API está indisponível."""
        with patch("core.views.fetch_all_bens_materiais", side_effect=Exception("offline")):
            response = client.get(reverse("home"))
        assert response.status_code == 200
