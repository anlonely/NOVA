from __future__ import annotations

import contextlib
import socket
import threading
import time
from typing import Iterator
from urllib.parse import urlsplit

try:
    import dns.exception
    import dns.resolver
except Exception:  # pragma: no cover - optional dependency during bootstrap
    dns = None
else:
    dns = dns.resolver


_CACHE_TTL_SEC = 300.0
_PATCH_LOCK = threading.RLock()
_ACTIVE_OVERRIDES: list[dict[str, tuple[str, ...]]] = []
_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_RESOLVE_CACHE: dict[tuple[tuple[str, ...], str], tuple[float, tuple[str, ...]]] = {}


def _split_tokens(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        raw_items = [str(item or "").strip() for item in value]
    else:
        raw_items = (
            str(value or "")
            .replace("\r", "\n")
            .replace(";", ",")
            .replace("|", ",")
            .splitlines()
        )
    tokens: list[str] = []
    for raw in raw_items:
        for part in raw.split(","):
            token = part.strip()
            if token:
                tokens.append(token)
    return tokens


def parse_dns_servers(value: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for token in _split_tokens(value):
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)


def parse_dns_hosts(value: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for token in _split_tokens(value):
        host = token
        if "://" in host:
            host = urlsplit(host).hostname or host
        host = host.strip().lower()
        if not host or host in seen:
            continue
        seen.add(host)
        ordered.append(host)
    return tuple(ordered)


def format_dns_csv(items: tuple[str, ...] | list[str]) -> str:
    return ", ".join(str(item).strip() for item in items if str(item).strip())


def resolve_host(host: str, dns_servers: tuple[str, ...], *, lifetime: float = 3.5, timeout: float = 1.5) -> tuple[str, ...]:
    normalized_host = str(host or "").strip().lower()
    nameservers = tuple(str(item).strip() for item in dns_servers if str(item).strip())
    if not normalized_host or not nameservers or dns is None:
        return ()

    cache_key = (nameservers, normalized_host)
    now = time.time()
    with _PATCH_LOCK:
        cached = _RESOLVE_CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL_SEC:
            return cached[1]

    resolver = dns.Resolver(configure=False)
    resolver.nameservers = list(nameservers)
    resolver.timeout = timeout
    resolver.lifetime = lifetime

    try:
        answers = resolver.resolve(normalized_host, "A", search=False)
        ips = tuple(dict.fromkeys(str(record) for record in answers))
    except Exception:
        with _PATCH_LOCK:
            _RESOLVE_CACHE.pop(cache_key, None)
        return ()

    with _PATCH_LOCK:
        if ips:
            _RESOLVE_CACHE[cache_key] = (time.time(), ips)
        else:
            _RESOLVE_CACHE.pop(cache_key, None)
    return ips


def target_hosts_for_url(url: str, dns_hosts: tuple[str, ...]) -> tuple[str, ...]:
    hostname = (urlsplit(str(url or "")).hostname or "").strip().lower()
    if not hostname:
        return ()
    for rule in dns_hosts:
        normalized_rule = str(rule or "").strip().lower()
        if not normalized_rule:
            continue
        if normalized_rule == hostname:
            return (hostname,)
        if normalized_rule.startswith("*.") and hostname.endswith(normalized_rule[1:]):
            return (hostname,)
        if normalized_rule.startswith(".") and hostname.endswith(normalized_rule):
            return (hostname,)
    return ()


def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    normalized_host = str(host or "").strip().lower()
    mapped_ips: tuple[str, ...] = ()
    with _PATCH_LOCK:
        for override in reversed(_ACTIVE_OVERRIDES):
            mapped_ips = override.get(normalized_host, ())
            if mapped_ips:
                break

    if not mapped_ips:
        return _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)

    results = []
    seen = set()
    for ip in mapped_ips:
        for item in _ORIGINAL_GETADDRINFO(ip, port, family, type, proto, flags):
            if item in seen:
                continue
            seen.add(item)
            results.append(item)
    return results or _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)


@contextlib.contextmanager
def dns_override(hosts: tuple[str, ...], dns_servers: tuple[str, ...]) -> Iterator[dict[str, tuple[str, ...]]]:
    normalized_hosts = parse_dns_hosts(hosts)
    nameservers = parse_dns_servers(dns_servers)
    if not normalized_hosts or not nameservers:
        yield {}
        return

    resolved: dict[str, tuple[str, ...]] = {}
    for host in normalized_hosts:
        ips = resolve_host(host, nameservers)
        if ips:
            resolved[host] = ips
    if not resolved:
        yield {}
        return

    with _PATCH_LOCK:
        _ACTIVE_OVERRIDES.append(resolved)
        socket.getaddrinfo = _patched_getaddrinfo
    try:
        yield resolved
    finally:
        with _PATCH_LOCK:
            try:
                _ACTIVE_OVERRIDES.remove(resolved)
            except ValueError:
                pass
            if _ACTIVE_OVERRIDES:
                socket.getaddrinfo = _patched_getaddrinfo
            else:
                socket.getaddrinfo = _ORIGINAL_GETADDRINFO
