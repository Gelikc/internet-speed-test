"""Measure download throughput with ten sequential HTTP GET requests."""

import argparse
import http.client
import math
import sys
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024


def http_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            return value
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("укажите корректный HTTP- или HTTPS-адрес")


def positive_timeout(value):
    try:
        timeout = float(value)
    except ValueError:
        timeout = 0
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("тайм-аут должен быть положительным числом")
    return timeout


def download(url, timeout):
    """Return body bytes and elapsed seconds after fully reading one response."""
    request = Request(url, headers={
        "User-Agent": "internet-speed-test/1.0",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    })
    size = 0
    started = time.perf_counter()
    with urlopen(request, timeout=timeout) as response:
        expected = response.headers.get("Content-Length")
        while chunk := response.read(CHUNK_SIZE):
            size += len(chunk)
        if expected is not None and size != int(expected):
            raise OSError("ответ получен не полностью (не совпадает Content-Length)")
    return size, time.perf_counter() - started


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Скорость скачивания по 10 последовательным запросам."
    )
    parser.add_argument("url", type=http_url, help="адрес файла (HTTP/HTTPS)")
    parser.add_argument(
        "--timeout", type=positive_timeout, default=30.0,
        help="тайм-аут ожидания сетевой операции в секундах (по умолчанию 30)",
    )
    args = parser.parse_args(argv)
    total_bytes = 0
    total_seconds = 0.0
    for number in range(1, REQUEST_COUNT + 1):
        try:
            size, elapsed = download(args.url, args.timeout)
        except (URLError, OSError, ValueError, http.client.HTTPException) as exc:
            print(f"Ошибка запроса {number}/{REQUEST_COUNT}: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nИзмерение прервано.", file=sys.stderr)
            return 130
        total_bytes += size
        total_seconds += elapsed
        print(f"Запрос {number}/{REQUEST_COUNT}: {size} байт за {elapsed:.3f} с")

    speed_mbps = total_bytes * 8 / total_seconds / 1_000_000
    print(f"\nСреднее время запроса: {total_seconds / REQUEST_COUNT:.3f} с")
    print(f"Общий объём: {total_bytes} байт ({total_bytes / 1_000_000:.3f} МБ)")
    print(f"Скорость скачивания: {speed_mbps:.3f} Мбит/с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
