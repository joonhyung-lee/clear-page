"""Serve only public page assets on localhost, never repository metadata."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse
import re

ROOT = Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def send_head(self):
        path=unquote(urlsplit(self.path).path)
        relative=Path(path.lstrip('/'))
        resolved=(ROOT/relative).resolve()
        code_public = path in ('/code', '/code/', '/code/index.html', '/code/code.css', '/code/code.js', '/code/catalog.js') or (
            path.startswith('/code/source/') and resolved.suffix == '.js')
        replanning_public = path in ('/replanning/', '/replanning/index.html', '/replanning/README.md') or (
            path.startswith('/replanning/videos-upright/') and resolved.suffix in {'.mp4', '.viser', '.js', '.png', '.json'}) or path in (
            '/replanning/previews/upright-palm-probe.mp4', '/replanning/previews/upright-palm-probe.png')
        if (any(part.startswith('.') or part=='..' for part in relative.parts)
            or not resolved.is_relative_to(ROOT)
            or not (path in ('/','/index.html','/.nojekyll') or path.startswith('/assets/') or replanning_public or code_public)):
            self.send_error(404);return None
        self.range_remaining=None
        if resolved.is_file() and resolved.suffix in {'.mp4', '.zip'}:
            size=resolved.stat().st_size
            header=self.headers.get('Range')
            start,end=0,size-1
            if header:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',header.strip())
                if not match or not any(match.groups()):
                    self.send_error(400);return None
                first,last=match.groups()
                if first:
                    start=int(first);end=min(int(last),size-1) if last else size-1
                else:
                    start=max(0,size-int(last))
                if start>=size or start>end:
                    self.send_response(416)
                    self.send_header('Content-Range',f'bytes */{size}')
                    self.send_header('Content-Length','0');self.end_headers();return None
            stream=resolved.open('rb');stream.seek(start)
            self.range_remaining=end-start+1
            self.send_response(206 if header else 200)
            self.send_header('Content-Type','video/mp4' if resolved.suffix=='.mp4' else 'application/zip')
            self.send_header('Accept-Ranges','bytes')
            self.send_header('Content-Length',str(self.range_remaining))
            if header:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            return stream
        return super().send_head()
    def copyfile(self,source,outputfile):
        try:
            if self.range_remaining is None:return super().copyfile(source,outputfile)
            remaining=self.range_remaining
            while remaining:
                chunk=source.read(min(65536,remaining))
                if not chunk:break
                outputfile.write(chunk);remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError):
            pass
    def list_directory(self,path): self.send_error(404);return None
    def end_headers(self):
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' blob: data:; worker-src 'self' blob:; media-src 'self' blob:; font-src 'self' data:; frame-src 'self'; object-src 'none'; base-uri 'self'")
        super().end_headers()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    print(f'Preview: http://localhost:{a.port}',flush=True)
    server.serve_forever()
