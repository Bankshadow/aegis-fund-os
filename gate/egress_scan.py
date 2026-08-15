"""Deterministic egress policy: every host in source must be declared.

Doctrine borrowed from Archestra (`archestra-ai/archestra`), no code borrowed —
that repo is AGPL-3.0-only and this one ships a public Worker. See
`docs/ARCHESTRA_ADOPTION.md`.

The idea worth taking is theirs: enforce an **allowlist**, deterministically,
outside the thing being guarded — rather than trusting a model, a reviewer, or a
convention to notice. At their scale that is a proxy in front of the LLM. At
ours it is this scan plus `integrations/egress-allowlist.json`, because our
hosts are pinned as string constants in eight different files with nothing
stopping a ninth from appearing.

Two checks, both fail-closed:

1. Every `http(s)://host` reachable from source is declared in the allowlist.
2. No declared host is marked as a live-trading venue.

Run standalone (prints the findings) or via `gate/eval_gate.py`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "integrations" / "egress-allowlist.json"

URL = re.compile(r"https?://([A-Za-z0-9._-]+)")

#: A scheme-less host still reaches the network. `webull-sandbox.server.ts`
#: pins `WEBULL_SANDBOX_HOST = "api.sandbox.webull.com"`, which the URL pattern
#: alone walks straight past — the first hole this scan found was its own.
#: Matching the naming convention rather than guessing at TLDs keeps it precise.
BARE_HOST = re.compile(
    r"""(?ix)
    \b[A-Za-z0-9_]*(?:HOST|URL|ENDPOINT|BASE_?URI|ORIGIN|DOMAIN)[A-Za-z0-9_]*
    \s*[:=]\s*
    ["'`](?:https?://)?([A-Za-z0-9._-]+\.[A-Za-z]{2,24})(?:[/:"'`]|$)
    """)

SCAN_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".ps1",
                 ".yml", ".yaml", ".jsonc", ".toml")

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv",
             "__pycache__", ".turbo", ".output", ".vinxi", ".wrangler",
             # `.pnpm-store` mirrors our own sources back at us, so every host
             # would be reported twice from a path nobody can fix.
             ".pnpm-store", ".pnpm", "coverage", "playwright-report",
             "data", "results", "logs"}

#: Hosts that are never real egress. RFC 2606 reserves `.test`/`.example`/
#: `.invalid` precisely so fixtures can use them, and loopback is not egress.
LOCAL = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
RESERVED_TLDS = (".test", ".example", ".invalid", ".localhost")

#: Line-level opt-out. Needed because this scan's own tests must plant
#: realistic hosts to prove the scan catches them, and a reserved-TLD fixture
#: would be filtered out before the detection under test ever ran. Suppressions
#: are counted and printed so they cannot quietly accumulate.
PRAGMA = "egress-scan: fixture"


def _reserved(host: str) -> bool:
    return (host in LOCAL
            or host.endswith(RESERVED_TLDS)
            or "." not in host)          # bare placeholders like `x`


def load_policy(path: Path = ALLOWLIST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_CACHE: dict = {}
SUPPRESSED = "_suppressed"


def scan(root: Path = ROOT, use_cache: bool = True) -> dict:
    """Map host -> sorted list of `relative/path:line` where it appears.

    Cached per root: `main` and the gate cases each need the same walk, and the
    tree is large enough that repeating it dominated the gate's runtime.
    """
    key = str(Path(root).resolve())
    if use_cache and key in _CACHE:
        return _CACHE[key]
    result = _scan_uncached(Path(root))
    if use_cache:
        _CACHE[key] = result
    return result


def suppressed_count(root: Path = ROOT) -> int:
    """How many lines opted out via the pragma."""
    return _COUNTS.get(str(Path(root).resolve()), 0)


_COUNTS: dict = {}


def _source_files(root: Path):
    """Yield scannable files, pruning skipped trees during the walk.

    `rglob` would enumerate every file under `node_modules` before filtering it
    out, which cost ~20s per scan; pruning `dirnames` in place skips those
    subtrees entirely.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(SCAN_SUFFIXES):
                yield Path(dirpath) / filename


def _scan_uncached(root: Path) -> dict:
    found: dict[str, set] = {}
    suppressed = 0
    for path in _source_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            hosts = URL.findall(line) + BARE_HOST.findall(line)
            if hosts and PRAGMA in line:
                suppressed += 1
                continue
            for host in hosts:
                host = host.lower().rstrip(".")
                if _reserved(host):
                    continue
                found.setdefault(host, set()).add(
                    f"{path.relative_to(root).as_posix()}:{number}")
    _COUNTS[str(root.resolve())] = suppressed
    return {host: sorted(sites) for host, sites in sorted(found.items())}


def undeclared(root: Path = ROOT, policy: dict = None) -> dict:
    policy = policy if policy is not None else load_policy()
    allowed = set(policy.get("hosts", {}))
    return {host: sites for host, sites in scan(root).items() if host not in allowed}


def live_trading_hosts(policy: dict = None) -> list:
    """Declared hosts that would put a live order on a real venue.

    The constitution forbids live trading, so this must always be empty. It is
    a data-level restatement of the law: adding such a host to the policy is
    the moment the gate should stop you, not the deploy afterwards.
    """
    policy = policy if policy is not None else load_policy()
    return sorted(host for host, entry in policy.get("hosts", {}).items()
                  if entry.get("live_trading"))


def stale_entries(root: Path = ROOT, policy: dict = None) -> list:
    """Declared hosts no longer present in source. Reported, never fatal."""
    policy = policy if policy is not None else load_policy()
    return sorted(set(policy.get("hosts", {})) - set(scan(root)))


def main() -> int:
    policy = load_policy()
    missing = undeclared(policy=policy)
    live = live_trading_hosts(policy)
    stale = stale_entries(policy=policy)

    for host, sites in missing.items():
        print(f"UNDECLARED  {host}")
        for site in sites[:5]:
            print(f"              {site}")
    for host in live:
        print(f"LIVE-TRADING  {host}  (forbidden by the project constitution)")
    for host in stale:
        print(f"stale (not fatal)  {host}  declared but no longer in source")

    if missing or live:
        print(f"BLOCKED: {len(missing)} undeclared host(s), {len(live)} live-trading host(s)")
        return 1
    print(f"egress OK: {len(policy.get('hosts', {}))} declared, "
          f"{len(scan())} in source, {len(stale)} stale, "
          f"{suppressed_count()} fixture line(s) suppressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
