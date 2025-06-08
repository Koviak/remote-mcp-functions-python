import types
from token_api_endpoints import register_token_api_endpoints

class DummyApp:
    def __init__(self):
        self.routes = []
    def route(self, route: str, methods: list[str]):
        def decorator(func):
            self.routes.append((route, tuple(methods), func))
            return func
        return decorator


def test_register_token_api_endpoints():
    app = DummyApp()
    register_token_api_endpoints(app)
    # Expect four routes to be registered
    routes = {r for r, _m, _f in app.routes}
    expected = {
        "tokens/{scope}",
        "tokens",
        "tokens/health",
        "tokens/refresh/{scope}",
    }
    assert expected.issubset(routes)
