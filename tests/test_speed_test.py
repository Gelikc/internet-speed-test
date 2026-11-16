import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
from pathlib import Path
import subprocess
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import speed_test

PAYLOAD = b"x" * (speed_test.CHUNK_SIZE * 2 + 17)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.paths.append(self.path)
        if self.path == "/error":
            self.send_error(503)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD if self.path == "/file" else PAYLOAD[:100])

    def log_message(self, *args):
        pass


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.paths = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_cli_downloads_ten_complete_responses(self):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(speed_test.__file__)), self.url + "/file"],
            capture_output=True, encoding="utf-8", timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.server.paths, ["/file"] * 10)
        self.assertIn(f"Общий объём: {len(PAYLOAD) * 10} байт", result.stdout)
        self.assertIn("Среднее время запроса:", result.stdout)
        self.assertIn("Мбит/с", result.stdout)

    def test_errors_stop_without_success_summary(self):
        for path in ("/error", "/truncated"):
            with self.subTest(path=path):
                self.server.paths.clear()
                output, errors = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    code = speed_test.main([self.url + path])
                self.assertEqual(code, 1)
                self.assertEqual(self.server.paths, [path])
                self.assertIn("Ошибка запроса 1/10", errors.getvalue())
                self.assertNotIn("Скорость скачивания:", output.getvalue())

    def test_invalid_arguments_do_not_make_requests(self):
        for arguments in (["file:///tmp/file"], [self.url, "--timeout", "nan"],
                          [self.url, "--timeout", "0"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    speed_test.main(arguments)
                self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.server.paths, [])


if __name__ == "__main__":
    unittest.main()
