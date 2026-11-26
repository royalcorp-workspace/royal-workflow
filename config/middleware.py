"""Custom middleware for Royal Workflow."""

from django_forms_workflows.services.notification_formatter import (
    reset_active_request_base_url,
    set_active_request_base_url,
)


class ActiveRequestBaseUrlMiddleware:
    """Capture the incoming request's scheme + host into a ContextVar so
    background email threads resolve absolute URLs from the active environment
    instead of falling back to localhost/127.0.0.1."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = None
        try:
            host = request.get_host()
            if host and host.split(":")[0].lower() != "testserver":
                origin = f"{request.scheme}://{host}".rstrip("/")
                token = set_active_request_base_url(origin)
        except Exception:
            token = None

        try:
            return self.get_response(request)
        finally:
            if token is not None:
                reset_active_request_base_url(token)
