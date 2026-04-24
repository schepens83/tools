import subprocess
import time
import urllib.request

import pytest


class StaticServer:
    def __init__(self, port):
        self.port = port
        self.proc = subprocess.Popen(
            ["python", "-m", "http.server", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/")
                break
            except Exception:
                time.sleep(0.1)

    def url(self, path=""):
        return f"http://127.0.0.1:{self.port}/{path}"

    def stop(self):
        self.proc.terminate()
        self.proc.wait()


@pytest.fixture
def static_server(unused_tcp_port):
    server = StaticServer(unused_tcp_port)
    yield server
    server.stop()
