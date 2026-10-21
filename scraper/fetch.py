"""Fetch a user-supplied URL without letting it reach the server's own network."""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import requests
from django.conf import settings

MAX_REDIRECTS = 5


class FetchError(Exception):
    pass


def check_url(url):
    """Reject anything but http(s) to public addresses – otherwise users could probe the LAN."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Nur http- und https-Links werden unterstützt.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise FetchError("Der Server des Links wurde nicht gefunden.") from None
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise FetchError("Links auf interne Adressen werden nicht abgerufen.")


def fetch_html(url):
    """Return (final_url, html). Redirects are followed by hand so every hop is checked."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": settings.SCRAPER_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    })
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        try:
            response = session.get(url, timeout=settings.SCRAPER_TIMEOUT, allow_redirects=False, stream=True)
        except requests.RequestException as exc:
            raise FetchError(f"Die Seite konnte nicht geladen werden ({exc.__class__.__name__}).") from exc
        with response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            if response.status_code >= 400:
                raise FetchError(f"Der Shop antwortete mit Fehler {response.status_code}.")
            if "html" not in response.headers.get("Content-Type", "text/html"):
                raise FetchError("Der Link zeigt nicht auf eine Webseite.")
            body = b""
            for chunk in response.iter_content(64 * 1024):
                body += chunk
                if len(body) > settings.SCRAPER_MAX_BYTES:
                    raise FetchError("Die Seite ist zu groß.")
            return url, body.decode(response.encoding or response.apparent_encoding or "utf-8", errors="replace")
    raise FetchError("Zu viele Weiterleitungen.")
