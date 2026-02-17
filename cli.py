#!/usr/bin/env python3
"""
Options Provider CLI — unified entry point for all operations.

Usage:
    python cli.py serve                       # Start API server
    python cli.py serve --port 9000           # Custom port
    python cli.py test                        # Run all tests
    python cli.py test -k greeks              # Filter tests
    python cli.py greeks gex AAPL             # Quick Greeks query
    python cli.py vol skew SPY                # Quick Vol query
    python cli.py full TSLA                   # Full analysis
    python cli.py health                      # Check server health
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

# ── Color helpers ────────────────────────────────────────────────────────

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _info(msg: str) -> None:
    print(f"{CYAN}▸{RESET} {msg}")


def _success(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def _error(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}", file=sys.stderr)


def _json_out(data: dict, compact: bool = False) -> None:
    """Pretty-print JSON output."""
    indent = None if compact else 2
    print(json.dumps(data, indent=indent, default=str))


# ── Command: serve ───────────────────────────────────────────────────────

def cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI server via uvicorn."""
    import uvicorn

    host = args.host
    port = args.port
    reload = args.reload
    workers = args.workers
    log_level = args.log_level

    _info(f"Starting Options Provider API on {BOLD}{host}:{port}{RESET}")
    _info(f"Reload={reload}  Workers={workers}  LogLevel={log_level}")

    bridge_url = os.environ.get("BRIDGE_URL", "http://localhost:8668")
    orats_token = os.environ.get("ORATS_TOKEN", "")
    _info(f"BRIDGE_URL={DIM}{bridge_url}{RESET}")
    _info(f"ORATS_TOKEN={DIM}{'***' + orats_token[-4:] if len(orats_token) > 4 else '(not set)'}{RESET}")
    print()

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level,
        access_log=False,
    )


# ── Command: test ────────────────────────────────────────────────────────

def cmd_test(args: argparse.Namespace) -> None:
    """Run the test suite via pytest."""
    import subprocess

    _info("Running test suite ...")
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]

    if args.filter:
        cmd += ["-k", args.filter]
    if args.coverage:
        cmd += ["--cov=.", "--cov-report=term-missing"]
    if args.extra:
        cmd += args.extra

    env = {**os.environ, "PYTHONPATH": "."}
    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)


# ── Command: greeks ──────────────────────────────────────────────────────

def cmd_greeks(args: argparse.Namespace) -> None:
    """Execute a Greeks exposure command directly (no server needed)."""
    from orats_provider import OratsClient, OratsConfig
    from orats_provider.greeks_exposure import commands

    config = OratsConfig.from_env()
    if not config.token:
        _error("ORATS_TOKEN not set. Export it or add to .env file.")
        sys.exit(1)

    client = OratsClient(config=config)
    _info(f"Greeks: {BOLD}{args.command}{RESET} → {args.symbol}")

    try:
        result = commands.execute(
            client, args.symbol, args.command,
            dte_min=args.dte_min, dte_max=args.dte_max,
            moneyness=args.moneyness,
        )
        _json_out(result.to_dict(), compact=args.compact)
    except Exception as e:
        _error(f"{e}")
        sys.exit(1)
    finally:
        client.close()


# ── Command: vol ─────────────────────────────────────────────────────────

def cmd_vol(args: argparse.Namespace) -> None:
    """Execute a Volatility analysis command directly (no server needed)."""
    from orats_provider import OratsClient, OratsConfig
    from orats_provider.volatility import commands

    config = OratsConfig.from_env()
    if not config.token:
        _error("ORATS_TOKEN not set. Export it or add to .env file.")
        sys.exit(1)

    client = OratsClient(config=config)
    _info(f"Volatility: {BOLD}{args.command}{RESET} → {args.symbol}")

    kwargs = dict(dte_min=args.dte_min, dte_max=args.dte_max, moneyness=args.moneyness)
    if args.command == "skew" and args.expiry_date:
        kwargs["expiry_date"] = args.expiry_date
    if args.command == "term":
        kwargs["target_dte"] = args.target_dte

    try:
        result = commands.execute(client, args.symbol, args.command, **kwargs)
        _json_out(result.to_dict(), compact=args.compact)
    except Exception as e:
        _error(f"{e}")
        sys.exit(1)
    finally:
        client.close()


# ── Command: full ────────────────────────────────────────────────────────

def cmd_full(args: argparse.Namespace) -> None:
    """Run full analysis for a symbol (offline, no server needed)."""
    from orats_provider import OratsConfig
    from provider.unified import UnifiedProvider

    config = OratsConfig.from_env()
    bridge_url = os.environ.get("BRIDGE_URL", "http://localhost:8668")

    _info(f"Full analysis: {BOLD}{args.symbol}{RESET}")

    provider = UnifiedProvider(bridge_url=bridge_url, orats_config=config)
    try:
        g_cmds = args.greeks.split(",") if args.greeks else None
        v_cmds = args.vol.split(",") if args.vol else None
        result = provider.full_analysis(args.symbol, greeks_commands_list=g_cmds, vol_commands_list=v_cmds)
        _json_out(result, compact=args.compact)
    except Exception as e:
        _error(f"{e}")
        sys.exit(1)
    finally:
        provider.close()


# ── Command: health ──────────────────────────────────────────────────────

def cmd_health(args: argparse.Namespace) -> None:
    """Check if the API server is running."""
    import urllib.request
    import urllib.error

    url = f"http://{args.host}:{args.port}/health"
    _info(f"Checking {url} ...")

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            _success(f"Server is healthy: {data}")
    except urllib.error.URLError as e:
        _error(f"Server unreachable: {e.reason}")
        sys.exit(1)
    except Exception as e:
        _error(f"Health check failed: {e}")
        sys.exit(1)


# ── Command: routes ──────────────────────────────────────────────────────

def cmd_routes(args: argparse.Namespace) -> None:
    """List all registered API routes."""
    from api.main import app

    _info("Registered API routes:\n")
    fmt = f"  {{method:<8}} {{path:<45}} {{name}}"
    print(f"{DIM}{fmt.format(method='METHOD', path='PATH', name='HANDLER')}{RESET}")
    print(f"  {'─' * 70}")
    for route in sorted(app.routes, key=lambda r: getattr(r, "path", "")):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        name = getattr(route, "name", "")
        if path and methods:
            for m in sorted(methods):
                print(fmt.format(method=m, path=path, name=name))


# ── Shared argument helpers ──────────────────────────────────────────────

def _add_query_args(parser: argparse.ArgumentParser) -> None:
    """Add common query parameters (dte, moneyness, compact)."""
    parser.add_argument("--dte-min", type=int, default=7, help="Minimum DTE (default: 7)")
    parser.add_argument("--dte-max", type=int, default=90, help="Maximum DTE (default: 90)")
    parser.add_argument("--moneyness", type=float, default=0.20, help="Moneyness range (default: 0.20)")
    parser.add_argument("--compact", "-c", action="store_true", help="Compact JSON output")


# ── Main parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="options-provider",
        description="Options Provider — unified options analysis CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Quick Examples:
              %(prog)s serve                        Start API server (port 9988)
              %(prog)s serve -p 9000 --reload       Dev mode on port 9000
              %(prog)s test                         Run all tests
              %(prog)s test -k greeks               Run only Greeks tests
              %(prog)s greeks gex AAPL              GEX exposure for AAPL
              %(prog)s greeks net_gex SPY            Net GEX for SPY
              %(prog)s vol skew TSLA                 Vol skew for TSLA
              %(prog)s vol term QQQ                  Term structure for QQQ
              %(prog)s full AAPL                     Full analysis
              %(prog)s health                        Check server health
              %(prog)s routes                        List all API routes
        """),
    )

    sub = parser.add_subparsers(dest="command", title="commands")

    # ── serve ──
    p_serve = sub.add_parser("serve", aliases=["s", "run"], help="Start the API server")
    p_serve.add_argument("-H", "--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    p_serve.add_argument("-p", "--port", type=int, default=9988, help="Bind port (default: 9988)")
    p_serve.add_argument("-w", "--workers", type=int, default=1, help="Worker count (default: 1)")
    p_serve.add_argument("--reload", "-r", action="store_true", help="Enable auto-reload (dev mode)")
    p_serve.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    p_serve.set_defaults(func=cmd_serve)

    # ── test ──
    p_test = sub.add_parser("test", aliases=["t"], help="Run the test suite")
    p_test.add_argument("-k", "--filter", help="Pytest -k filter expression")
    p_test.add_argument("--coverage", "--cov", action="store_true", help="Enable coverage report")
    p_test.add_argument("extra", nargs="*", help="Additional pytest arguments")
    p_test.set_defaults(func=cmd_test)

    # ── greeks ──
    p_greeks = sub.add_parser("greeks", aliases=["g"], help="Execute a Greeks command (offline)")
    p_greeks.add_argument("cmd_name", metavar="command",
                          choices=["gex", "net_gex", "gex_distribution", "gex_3d",
                                   "dex", "net_dex", "vex", "net_vex", "vanna"],
                          help="Greeks command")
    p_greeks.add_argument("symbol", help="Ticker symbol (e.g. AAPL)")
    _add_query_args(p_greeks)
    p_greeks.set_defaults(func=lambda a: cmd_greeks(type(a)(**{
        **vars(a), "command": a.cmd_name
    })))

    # ── vol ──
    p_vol = sub.add_parser("vol", aliases=["v"], help="Execute a Volatility command (offline)")
    p_vol.add_argument("cmd_name", metavar="command",
                       choices=["skew", "term", "surface"],
                       help="Volatility command")
    p_vol.add_argument("symbol", help="Ticker symbol (e.g. AAPL)")
    p_vol.add_argument("--expiry-date", help="Target expiry (for skew)")
    p_vol.add_argument("--target-dte", type=int, default=30, help="Target DTE for term (default: 30)")
    _add_query_args(p_vol)
    p_vol.set_defaults(func=lambda a: cmd_vol(type(a)(**{
        **vars(a), "command": a.cmd_name
    })))

    # ── full ──
    p_full = sub.add_parser("full", aliases=["f"], help="Full analysis for a symbol")
    p_full.add_argument("symbol", help="Ticker symbol")
    p_full.add_argument("--greeks", help="Comma-separated Greeks commands (default: gex,dex,vex,vanna)")
    p_full.add_argument("--vol", help="Comma-separated Vol commands (default: skew,term,surface)")
    p_full.add_argument("--compact", "-c", action="store_true", help="Compact JSON output")
    p_full.set_defaults(func=cmd_full)

    # ── health ──
    p_health = sub.add_parser("health", aliases=["h"], help="Check server health")
    p_health.add_argument("-H", "--host", default="localhost")
    p_health.add_argument("-p", "--port", type=int, default=9988)
    p_health.set_defaults(func=cmd_health)

    # ── routes ──
    p_routes = sub.add_parser("routes", help="List all API routes")
    p_routes.set_defaults(func=cmd_routes)

    return parser


def main() -> None:
    # Auto-load .env file if present
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print(f"\n{YELLOW}Tip:{RESET} Use '{parser.prog} serve' to start the server quickly.")
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
