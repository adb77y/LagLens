"""Launch the local desktop application; --serve also supports browser-based use."""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import webbrowser
from pathlib import Path

from . import __version__
from .capture import CaptureManager
from .reports import html_report, svg_report
from .server import make_server


def main():
    parser = argparse.ArgumentParser(description='LagLens: capture a stutter, compare the fix.')
    parser.add_argument('--serve', action='store_true', help='Serve locally without opening a window')
    parser.add_argument('--browser', action='store_true', help='Open the default browser instead of a desktop window')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--ready-file',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--version',action='version',version=__version__)
    args = parser.parse_args()
    data_dir = args.data_dir or Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'LagLens'/'captures'
    manager = CaptureManager(data_dir)
    ui = Path(__file__).resolve().parent/'ui'
    server = make_server(manager,ui,args.port)
    url = f'http://127.0.0.1:{server.server_port}'
    if args.ready_file:
        args.ready_file.write_text(json.dumps({'url':url,'pid':os.getpid()}),encoding='utf-8')
    if args.serve:
        print(f'LagLens {__version__}: {url}',flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            manager.stop()
            server.server_close()
        return
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()

    class DesktopApi:
        def save_report(self,record_id,fmt):
            record = manager.get(record_id)
            if fmt not in ('svg','html','json'):
                raise ValueError('Unsupported format.')
            exports = data_dir.parent/'exports'
            exports.mkdir(parents=True,exist_ok=True)
            text = svg_report(record) if fmt=='svg' else html_report(record) if fmt=='html' else json.dumps(record,indent=2)
            path = exports/f'LagLens-{record_id[:8]}.{fmt}'
            path.write_text(text,encoding='utf-8')
            return str(path)

        def open_exports(self):
            path = data_dir.parent/'exports'
            path.mkdir(parents=True,exist_ok=True)
            if os.name=='nt':
                os.startfile(path)

    try:
        if args.browser:
            webbrowser.open(url)
            thread.join()
        else:
            import webview
            webview.create_window('LagLens',url,js_api=DesktopApi(),width=1320,height=900,
                                  min_size=(720,600),background_color='#171719')
            webview.start(gui='edgechromium' if os.name=='nt' else None)
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()
        server.shutdown()
        server.server_close()


if __name__=='__main__':
    main()
