"""Loopback HTTP adapters for integration tests only; excluded from release image."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError
from .core import DESCRIPTOR


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def send(url, event):
    request = Request(url, data=json.dumps(event).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=2) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


def server(kind, factory):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def reply(self, status, obj):
            raw = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            self.reply(200, DESCRIPTOR) if kind == 'provider' and self.path == '/.well-known/mitosis-capabilities.json' else self.reply(404, {'error': 'not found'})
        def do_POST(self):
            if self.path != ('/v1/work-packages' if kind == 'provider' else '/callback'):
                return self.reply(404, {'error': 'not found'})
            instance = None
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536: raise ValueError('body size')
                def unique(pairs):
                    obj = {}
                    for key, value in pairs:
                        if key in obj: raise ValueError('duplicate JSON key')
                        obj[key] = value
                    return obj
                body = json.loads(self.rfile.read(size), object_pairs_hook=unique)
                instance = factory()
                if kind == 'provider':
                    result = {'providerRunId': instance.dispatch(self.headers.get('Idempotency-Key'), body)}
                    self.reply(202, result)
                else:
                    self.reply(200, {'result': instance.receive(body)})
            except (ValueError, TypeError, KeyError):
                self.reply(422, {'error': 'contract validation failed'})
            finally:
                if instance: instance.db.close()
    class LocalServer(HTTPServer):
        def get_request(self):
            sock, address = super().get_request()
            sock.settimeout(3)
            return sock, address
    return LocalServer(('127.0.0.1', 0), Handler)
