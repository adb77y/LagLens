"""Download only the official, SHA-256-pinned PresentMon console application."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='2.6.0'
SHA256='b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af'
URL=f'https://github.com/GameTechDev/PresentMon/releases/download/v{VERSION}/PresentMon-{VERSION}-x64.exe'


def main():
    path=ROOT/'vendor/PresentMon.exe'
    path.parent.mkdir(exist_ok=True)
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==SHA256:
        print('Official PresentMon 2.6.0 is already verified.');return
    request=urllib.request.Request(URL,headers={'User-Agent':'LagLens-build/0.1'})
    data=urllib.request.urlopen(request,timeout=60).read()
    if hashlib.sha256(data).hexdigest()!=SHA256:
        raise SystemExit('Checksum mismatch; refusing to install the file.')
    temporary=path.with_suffix('.download')
    temporary.write_bytes(data)
    temporary.replace(path)
    print(f'PresentMon {VERSION} downloaded and verified ({len(data):,} bytes).')


if __name__=='__main__':main()
