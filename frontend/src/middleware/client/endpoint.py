from typing import Optional


class Endpoint:
    def __init__(self, ip: str, port: int, route: Optional[str] = None):
        self.ip = ip[8 if ip.startswith('https://') else 7 if ip.startswith('http://') else 0:]
        self.port = port

        if not route or route == '/':
            self.route = None
        else:
            self.route = route[1 if route.startswith('/') else 0:]

    def __call__(self, route: Optional[str] = None):
        if not route:
            return self
        endpoint = Endpoint(*self)
        endpoint.route = route
        return Endpoint(*endpoint)  # Re-instantiating fixes slashes in `route`

    def _to_string(self):
        ip = self.ip if self.ip else 'localhost'
        port = f":{self.port}" if self.port else ''
        route = f"/{self.route}" if self.route else ''
        return f"http://{ip}{port}{route}"

    def __str__(self):
        return self._to_string()

    def __repr__(self):
        return self._to_string()

    def __unicode__(self):
        return self._to_string()

    def __iter__(self):
        yield self.ip if self.ip else 'localhost'
        if self.port:
            yield self.port
        if self.route:
            yield self.route
