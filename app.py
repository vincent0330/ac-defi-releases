"""Stateless read-only site. No signing, transaction, or operator endpoints."""
import hashlib
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent


def configuration(env=None):
    env = os.environ if env is None else env
    manifest_bytes = (ROOT / 'deployment-manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    errors = []
    if env.get('APP_NETWORK', 'sepolia') != 'sepolia': errors.append('unsupported_network')
    if env.get('CHAIN_ID', '11155111') != '11155111': errors.append('chain_id_mismatch')
    expected = env.get('DEPLOYMENT_MANIFEST_SHA256')
    if expected and expected != digest: errors.append('manifest_hash_mismatch')
    if manifest['network'] != 'sepolia' or manifest['chainId'] != 11155111: errors.append('manifest_network_mismatch')
    # This release has no approved deployment. Configuration cannot promote it to verified.
    if any(env.get(k) for k in ('SEPOLIA_RPC_URL', 'SEPOLIA_VAULT_ADDRESS', 'SEPOLIA_USDC_ADDRESS')):
        errors.append('deployment_not_approved')
    if manifest['verification'] != 'unconfigured' or manifest['vault'] is not None or manifest['usdc'] is not None:
        errors.append('unsupported_deployment_manifest')
    return {'network': 'sepolia', 'chainId': 11155111, 'verified': False,
            'readOnly': True, 'transactionsEnabled': False, 'errors': errors or ['missing_approved_deployment'],
            'manifestSha256': digest, 'rpcStatus': 'unavailable'}


def metadata():
    meta = json.loads((ROOT / 'build-info.json').read_text())
    conf = configuration()
    return {**meta, 'network': conf['network'], 'chainId': conf['chainId'],
            'manifestSha256': conf['manifestSha256'], 'readOnly': True,
            'chainVerified': False, 'releaseState': 'PREPARED'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def respond(self, status, body, mime='application/json; charset=utf-8'):
        if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/health':
            return self.respond(200, {'status': 'ok', 'service': 'ac-defi-read-only', 'chainId': 11155111, 'rpcRequired': False})
        if path == '/release': return self.respond(200, metadata())
        if path == '/api/status': return self.respond(503, configuration())
        files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if path in files:
            filename, mime = files[path]
            return self.respond(200, (ROOT / 'public' / filename).read_bytes(), mime + '; charset=utf-8')
        self.respond(404, {'error': 'not_found'})
    def do_POST(self): self.respond(405, {'error': 'read_only'})
    do_PUT = do_DELETE = do_PATCH = do_POST


def main():
    port = int(os.environ.get('PORT', '8080'))
    if not 1 <= port <= 65535: raise ValueError('PORT out of range')
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()


if __name__ == '__main__': main()
