"""CLI entry point for LCCG."""

from __future__ import annotations

import json
import time as _time
from pathlib import Path

import click
import httpx
import structlog
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lccg.config.loader import load_config
from lccg.provider.registry import ProviderRegistry
from lccg.router.engine import RouterEngine
from lccg.server.app import create_app

console = Console()


def _setup_logging(level: str, log_dir: str | None = None, log_queue=None) -> None:
    """Configure structlog with session-based file logging.

    Each session creates a new log file: lccg-{YYYYMMDDHHmmss}.log
    Auto-rotates at 50MB, keeps max 3 files per session.

    If log_queue is provided, log entries are also pushed to the queue for SSE streaming.

    Level can be comma-separated (e.g. "info,warning,error") to output only specific levels.
    The most verbose level is used as the structlog filtering threshold.
    """
    import logging as _logging
    from logging.handlers import RotatingFileHandler

    # Parse level: support "info,warning,error" or single "info"
    level_names = [lv.strip().lower() for lv in level.split(",") if lv.strip()]
    level_map = {"debug": 10, "info": 20, "warning": 30, "error": 40}
    selected_levels = {lv for lv in level_names if lv in level_map}

    if len(selected_levels) > 1:
        # Multi-level: use most verbose as threshold, filter by selected set
        log_level = min(level_map[lv] for lv in selected_levels)
        _selected_level_names = selected_levels
    elif len(selected_levels) == 1:
        lv = next(iter(selected_levels))
        log_level = level_map[lv]
        _selected_level_names = None  # single level, no extra filtering
    else:
        log_level = 20  # default info
        _selected_level_names = None

    # Custom filtering wrapper for multi-level selection
    def _level_filter_processor():
        """Filter log entries to only include selected levels."""
        def processor(logger, method_name, event_dict):
            if _selected_level_names and method_name not in _selected_level_names:
                raise structlog.DropEvent
            return event_dict
        return processor

    if log_dir:
        log_path = Path(log_dir).expanduser()
        log_path.mkdir(parents=True, exist_ok=True)

        # Session-based log file name
        session_time = _time.strftime("%Y%m%d%H%M%S")
        log_file = log_path / f"lccg-{session_time}.log"

        # Rotating file handler for JSON output
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(_logging.Formatter("%(message)s"))

        # File-only logger
        file_logger = _logging.getLogger("lccg.file")
        file_logger.setLevel(log_level)
        file_logger.handlers.clear()
        file_logger.addHandler(file_handler)
        file_logger.propagate = False

        # Clean up old log files
        _cleanup_old_logs(log_path, keep=3)

        # structlog config: console rendering, with JSON appended to file logger
        processors = [
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]
        if _selected_level_names:
            processors.append(_level_filter_processor())
        if log_queue is not None:
            processors.append(_queue_processor(log_queue))
        processors.append(_file_and_console_processor())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
        )
    else:
        processors = [
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]
        if _selected_level_names:
            processors.append(_level_filter_processor())
        if log_queue is not None:
            processors.append(_queue_processor(log_queue))
        processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
        )


def _file_and_console_processor():
    """Returns a processor that renders console output and also writes JSON to file."""
    console = structlog.dev.ConsoleRenderer()
    file_log = None

    def processor(logger, method_name, event_dict):
        nonlocal file_log
        if file_log is None:
            import logging as _logging
            file_log = _logging.getLogger("lccg.file")

        # Console output
        console_output = console(logger, method_name, event_dict)

        # JSON to file
        try:
            json_line = json.dumps(event_dict, ensure_ascii=False, default=str)
            getattr(file_log, method_name, file_log.info)(json_line)
        except Exception:
            pass

        return console_output

    return processor


def _queue_processor(log_queue):
    """Returns a processor that pushes log entries to an asyncio Queue for SSE streaming."""
    import asyncio as _asyncio

    def processor(logger, method_name, event_dict):
        if log_queue is not None:
            try:
                line = json.dumps(event_dict, ensure_ascii=False, default=str)
                log_queue.put_nowait(line)
            except Exception:
                pass  # Queue full or other error — drop silently
        return event_dict

    return processor


def _cleanup_old_logs(log_dir: Path, keep: int = 3) -> None:
    """Remove old log files, keeping only the N most recent."""
    try:
        logs = sorted(log_dir.glob("lccg-*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
        for old_log in logs[keep:]:
            old_log.unlink()
    except Exception:
        pass


@click.group()
@click.version_option(package_name="lccg")
def cli() -> None:
    """LCCG - Local Claude Code Gateway."""


@cli.command()
@click.option(
    "-c", "--config",
    type=click.Path(exists=False),
    default=None,
    help="Path to config file (default: ~/.lccg/config.yaml)",
)
@click.option("--host", default=None, help="Host to bind to (overrides config)")
@click.option("--port", default=None, type=int, help="Port to bind to (overrides config)")
@click.option("--log-level", default=None, help="Log level (overrides config)")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload on code changes")
def serve(
    config: str | None,
    host: str | None,
    port: int | None,
    log_level: str | None,
    reload: bool = False,
) -> None:
    """Start the LCCG gateway server."""
    # Load config
    try:
        gateway_config = load_config(config)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise SystemExit(1)

    # Apply CLI overrides
    if host:
        gateway_config.server.host = host
    if port:
        gateway_config.server.port = port
    if log_level:
        gateway_config.logging.level = log_level
    if reload:
        gateway_config.server.reload = True

    # Setup logging with queue for UI log streaming
    import asyncio as _asyncio
    log_queue = _asyncio.Queue(maxsize=1000)
    _setup_logging(gateway_config.logging.level, gateway_config.logging.log_dir, log_queue=log_queue)
    logger = structlog.get_logger()

    # Log provider API key status
    for p in gateway_config.providers:
        key_display = f"{p.api_key[:8]}...{p.api_key[-4:]}" if p.api_key and len(p.api_key) > 12 else ("(empty)" if not p.api_key else p.api_key)
        masked = "***" if p.api_key else "(empty)"
        logger.info("provider.config", name=p.name, type=p.type.value, base_url=p.base_url, api_key=masked)

    # Build provider registry and router
    try:
        registry = ProviderRegistry(gateway_config)
        router = RouterEngine(gateway_config, registry)
    except Exception as e:
        console.print(f"[red]Initialization error:[/red] {e}")
        raise SystemExit(1)

    # Create FastAPI app
    config_path_val = config if config else str(Path.home() / ".lccg" / "config.yaml")
    app = create_app(gateway_config, registry, router, config_path=config_path_val, log_queue=log_queue)

    # Display startup banner
    console.print(
        Panel(
            f"[bold green]LCCG Gateway Server[/bold green]\n\n"
            f"  Host:     [cyan]{gateway_config.server.host}[/cyan]\n"
            f"  Port:     [cyan]{gateway_config.server.port}[/cyan]\n"
            f"  Providers: [cyan]{', '.join(registry.provider_names)}[/cyan]\n\n"
            f"  UI:       [cyan]http://{gateway_config.server.host}:{gateway_config.server.port}/ui/[/cyan]\n\n"
            f"  Set [yellow]ANTHROPIC_BASE_URL=http://{gateway_config.server.host}:{gateway_config.server.port}[/yellow]\n"
            f"  to use this gateway with Claude Code.",
            title="Local Claude Code Gateway",
            border_style="green",
        )
    )

    logger.info(
        "server.starting",
        host=gateway_config.server.host,
        port=gateway_config.server.port,
        providers=registry.provider_names,
    )

    # Start server — uvicorn only accepts a single log level, use the most verbose one
    uvicorn_log_level = gateway_config.logging.level.split(",")[0].strip().lower()

    uvicorn.run(
        app,
        host=gateway_config.server.host,
        port=gateway_config.server.port,
        log_level=uvicorn_log_level,
        reload=gateway_config.server.reload,
        reload_dirs=["src/lccg"] if gateway_config.server.reload else None,
    )


if __name__ == "__main__":
    cli()


@cli.command()
@click.option("--host", default="127.0.0.1", help="LCCG server host")
@click.option("--port", default=8765, type=int, help="LCCG server port")
def status(host: str, port: int) -> None:
    """Show LCCG gateway status and statistics."""
    url = f"http://{host}:{port}/v1/stats"
    try:
        resp = httpx.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        console.print(f"[red]Cannot connect to LCCG server at {url}[/red]")
        console.print("Is the server running? Start with: [cyan]lccg serve[/cyan]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    summary = data.get("summary", {})
    providers = data.get("providers", {})
    recent = data.get("recent", [])

    # Summary panel
    console.print(
        Panel(
            f"  Total Requests:  [cyan]{summary.get('total_requests', 0)}[/cyan]\n"
            f"  Success:         [green]{summary.get('success', 0)}[/green]  "
            f"Error: [red]{summary.get('error', 0)}[/red]\n"
            f"  Input Tokens:    [cyan]{summary.get('total_input_tokens', 0):,}[/cyan]  "
            f"Output Tokens: [cyan]{summary.get('total_output_tokens', 0):,}[/cyan]\n"
            f"  Avg Latency:     [cyan]{summary.get('avg_latency_ms', 0)}ms[/cyan]  "
            f"Uptime: [cyan]{summary.get('uptime_seconds', 0)}s[/cyan]",
            title="LCCG Status",
            border_style="green",
        )
    )

    # Per-provider table
    if providers:
        table = Table(title="Provider Stats")
        table.add_column("Provider", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("OK", style="green", justify="right")
        table.add_column("Error", style="red", justify="right")
        table.add_column("Input Tokens", justify="right")
        table.add_column("Output Tokens", justify="right")
        table.add_column("Avg Latency", justify="right")

        for name, s in providers.items():
            table.add_row(
                name,
                str(s["total"]),
                str(s["success"]),
                str(s["error"]),
                f"{s['total_input_tokens']:,}",
                f"{s['total_output_tokens']:,}",
                f"{s['avg_latency_ms']}ms",
            )
        console.print(table)

    # Recent requests
    if recent:
        console.print(f"\n[bold]Recent {len(recent)} Requests:[/bold]")
        for r in recent:
            status_color = "green" if r["status"] == "success" else "red"
            console.print(
                f"  [{status_color}]{r['status']:7}[/{status_color}] "
                f"[cyan]{r['provider']}[/cyan] "
                f"{r['model']} "
                f"{r['latency_ms']}ms "
                f"in:{r['input_tokens']} out:{r['output_tokens']}"
                + (f" ({r['error'][:50]})" if r.get("error") else "")
            )
