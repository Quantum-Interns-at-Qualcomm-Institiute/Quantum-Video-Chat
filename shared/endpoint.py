class Endpoint:
    def __init__(self, ip: str, port: int, route: str = None):
        if not ip:
            self.ip = None
        elif ip.startswith('https://'):
            self.ip = ip[8:]
        elif ip.startswith('http://'):
            self.ip = ip[7:]
        else:
            self.ip = ip

        self.port = port

        if not route:
            self.route = None
        elif route == '/':
            self.route = None
        elif route.startswith('/'):
            self.route = route[1:]
        else:
            self.route = route

    def __call__(self, route: str):
        if not route:
            return self
        endpoint = Endpoint(*self)
        endpoint.route = route
        return Endpoint(*endpoint)  # Re-instantiating fixes slashes in `route`

    def to_string(self):
        ip = self.ip if self.ip else 'localhost'
        port = f":{self.port}" if self.port else ''
        route = f"/{self.route}" if self.route else ''
        return f"http://{ip}{port}{route}"

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()

    def __unicode__(self):
        return self.to_string()

    def __iter__(self):
        yield self.ip if self.ip else 'localhost'
        if self.port:
            yield self.port
        if self.route:
            yield self.route
