"""Loopback-only API with same-origin checks and a per-launch write token."""
from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .analysis import compare
from .capture import processes
from .reports import html_report, svg_report


def make_server(manager, ui_path, port=0):
    token = secrets.token_urlsafe(32)
    ui_path = Path(ui_path).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, body, status=200, content_type='application/json', download=None):
            if not isinstance(body, (str, bytes)):
                body = json.dumps(body, allow_nan=False)
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type + ('; charset=utf-8' if 'font' not in content_type else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            if download:
                self.send_header('Content-Disposition', f'attachment; filename="{download}"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host():
                return self.send({'error':'Invalid host.'},403)
            path = urlsplit(self.path).path
            try:
                if path == '/api/status':
                    return self.send(manager.snapshot())
                if path == '/api/processes':
                    return self.send(processes())
                if path == '/api/sessions':
                    return self.send(manager.list_records())
                if path.startswith('/api/session/'):
                    record = manager.get(path.rsplit('/',1)[1])
                    return self.send({k:v for k,v in record.items() if k not in ('frames',)})
                if path.startswith('/export/'):
                    filename = path.rsplit('/',1)[1]
                    record_id, fmt = filename.rsplit('.',1)
                    record = manager.get(record_id)
                    if fmt == 'svg':
                        return self.send(svg_report(record),content_type='image/svg+xml',download='LagLens-report.svg')
                    if fmt == 'html':
                        return self.send(html_report(record),content_type='text/html',download='LagLens-report.html')
                    if fmt == 'json':
                        return self.send(record,download='LagLens-capture.json')
                    raise ValueError('Unsupported export format.')
                relative = 'index.html' if path == '/' else path.lstrip('/')
                file = (ui_path / relative).resolve()
                if not file.is_relative_to(ui_path) or not file.is_file():
                    return self.send({'error':'Not found.'},404)
                data = file.read_bytes()
                if file.name == 'index.html':
                    data = data.replace(b'__WRITE_TOKEN__', token.encode())
                mime = {'.html':'text/html','.css':'text/css','.js':'text/javascript',
                        '.svg':'image/svg+xml','.ttf':'font/ttf','.woff2':'font/woff2'}.get(file.suffix,'application/octet-stream')
                return self.send(data,content_type=mime)
            except (ValueError, OSError, KeyError) as error:
                return self.send({'error':str(error)},400)

        def do_POST(self):
            origin = self.headers.get('Origin')
            expected = f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or (origin and origin != expected) or not secrets.compare_digest(self.headers.get('X-LagLens-Token',''), token):
                return self.send({'error':'This request is not from the LagLens window.'},403)
            try:
                length = int(self.headers.get('Content-Length',0))
                if not 0 < length <= 34*1024*1024:
                    raise ValueError('Request must be smaller than 34 MB.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict):
                    raise ValueError('Expected a JSON object.')
                path = urlsplit(self.path).path
                if path == '/api/start':
                    result = manager.start(body.get('pid'), body.get('target',60), body.get('duration',120), body.get('probe',False))
                elif path == '/api/stop':
                    result = manager.stop()
                elif path == '/api/mark':
                    result = manager.mark()
                elif path == '/api/demo':
                    result = manager.samples()
                elif path == '/api/import':
                    target = body.get('target',60)
                    if target not in (30,60,90,120,144,165,240):
                        raise ValueError('Invalid target FPS.')
                    result = manager.import_csv(str(body.get('csv','')),str(body.get('name',''))[:120],target)
                    result = {k:v for k,v in result.items() if k != 'frames'}
                elif path == '/api/compare':
                    result = compare(manager.get(str(body.get('before',''))), manager.get(str(body.get('after',''))))
                else:
                    return self.send({'error':'Unknown action.'},404)
                return self.send(result)
            except (ValueError, TypeError, OSError, KeyError) as error:
                return self.send({'error':str(error)},400)

    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads = True
    return server
