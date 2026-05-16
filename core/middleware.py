from api_client.client import set_api_auth_token


class ApiAuthTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_api_auth_token(request.session.get("api_auth_token", ""))
        return self.get_response(request)
