"""Network endpoint representation with URL construction."""

from __future__ import annotations


class Endpoint:
    """Represents a network endpoint with IP, port, and optional route."""

    def __init__(self, ip: str, port: int, route: str | None = None):
        """Initialize endpoint, stripping protocol prefixes from IP."""
        if not ip:
            self.ip = None
        elif ip.startswith("https://"):
            self.ip = ip[8:]
        elif ip.startswith("http://"):
            self.ip = ip[7:]
        else:
            self.ip = ip

        self.port = port

        if not route or route == "/":
            self.route = None
        elif route.startswith("/"):
            self.route = route[1:]
        else:
            self.route = route

    def __call__(self, route: str):
        """Return a new Endpoint with the given route appended."""
        if not route:
            return self
        endpoint = Endpoint(*self)
        endpoint.route = route
        return Endpoint(*endpoint)  # Re-instantiating fixes slashes in `route`

    def to_string(self):
        """Build the full URL string for this endpoint."""
        from shared.ssl_utils import get_ssl_context  # noqa: PLC0415
        scheme = "https" if get_ssl_context() else "http"
        ip = self.ip or "localhost"
        port = f":{self.port}" if self.port else ""
        route = f"/{self.route}" if self.route else ""
        return f"{scheme}://{ip}{port}{route}"

    def __str__(self):
        """Return string representation."""
        return self.to_string()

    def __repr__(self):
        """Return detailed string representation."""
        return self.to_string()

    def __unicode__(self):
        """Return unicode string representation."""
        return self.to_string()

    def __iter__(self):
        """Yield IP, port, and route components."""
        yield self.ip or "localhost"
        if self.port is not None:
            yield self.port
        if self.route:
            yield self.route
