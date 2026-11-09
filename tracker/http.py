from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import httpx

USER_AGENT = "eu-swe-2027-tracker (+https://github.com/luca7ok/job-scrapper)"
TIMEOUT = 20.0
RETRIES = 2
MIN_HOST_INTERVAL = 0.5
MAX_CONCURRENCY = 4


class PoliteClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*"},
            follow_redirects=True,
            limits=httpx.Limits(max_connections=MAX_CONCURRENCY * 2),
        )
        self._sem = threading.Semaphore(MAX_CONCURRENCY)
        self._host_locks: dict[str, threading.Lock] = {}
        self._host_last: dict[str, float] = {}
        self._meta = threading.Lock()

    def _host_lock(self, host: str) -> threading.Lock:
        with self._meta:
            if host not in self._host_locks:
                self._host_locks[host] = threading.Lock()
            return self._host_locks[host]

    def _wait_host(self, host: str) -> None:
        lock = self._host_lock(host)
        with lock:
            last = self._host_last.get(host, 0.0)
            delay = MIN_HOST_INTERVAL - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
            self._host_last[host] = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(RETRIES + 1):
            self._wait_host(host)
            try:
                with self._sem:
                    resp = self._client.request(method, url, **kwargs)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < RETRIES:
                    time.sleep(1.5 * (2 ** attempt))
                    continue
                return resp
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < RETRIES:
                    time.sleep(1.5 * (2 ** attempt))
                    continue
                raise
        raise last_exc or RuntimeError("request failed")

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        self._client.close()


_shared: PoliteClient | None = None


def client() -> PoliteClient:
    global _shared
    if _shared is None:
        _shared = PoliteClient()
    return _shared
