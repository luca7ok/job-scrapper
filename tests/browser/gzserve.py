import gzip, http.server, sys, os
ROOT = sys.argv[1]; PORT = int(sys.argv[2])
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path): path = os.path.join(path, "index.html")
        if not os.path.isfile(path) or "gzip" not in self.headers.get("Accept-Encoding", ""):
            return super().send_head()
        body = gzip.compress(open(path, "rb").read())
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=600")
        self.end_headers()
        import io; return io.BytesIO(body)
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
