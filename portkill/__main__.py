"""Entry point for PortKill CLI."""

import argparse
import sys


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="portkill",
        description="TUI for managing ports and processes",
    )

    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="Show version and exit",
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        help="Filter by specific port on startup",
    )

    parser.add_argument(
        "-k", "--kill",
        type=int,
        metavar="PORT",
        help="Kill all processes on PORT and exit (non-interactive)",
    )

    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all dev processes and exit (non-interactive)",
    )

    parser.add_argument(
        "--ports-only",
        action="store_true",
        help="With --list, show only processes with open ports",
    )

    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Use SIGKILL instead of SIGTERM (with --kill)",
    )

    args = parser.parse_args()

    if args.version:
        from portkill import __version__
        print(f"portkill {__version__}")
        return 0

    if args.list:
        return _list_processes(ports_only=args.ports_only)

    if args.kill is not None:
        return _kill_port(args.kill, args.force)

    # Run TUI
    from portkill.app import PortKillApp
    app = PortKillApp()
    app.run()
    return 0


def _list_processes(ports_only: bool = False):
    """List all development processes (non-interactive)."""
    from rich.console import Console
    from rich.table import Table

    from portkill.services.process_manager import ProcessManager

    console = Console()
    manager = ProcessManager()

    if ports_only:
        processes = manager.get_port_processes()
        title = "Processes with Open Ports"
    else:
        processes = manager.get_dev_processes(include_ports=True)
        title = "Development Processes"

    if not processes:
        console.print("[yellow]No development processes found.[/yellow]")
        return 0

    table = Table(title=title)
    table.add_column("PID", style="cyan")
    table.add_column("Port", style="green")
    table.add_column("Proto")
    table.add_column("Status")
    table.add_column("Service", style="magenta")
    table.add_column("Command")

    for proc in processes:
        port_str = str(proc.port) if proc.port > 0 else "-"
        table.add_row(
            str(proc.pid),
            port_str,
            proc.protocol if proc.port > 0 else "-",
            proc.status_icon,
            proc.service_type.value,
            proc.short_command,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(processes)} processes[/dim]")
    return 0


def _kill_port(port: int, force: bool):
    """Kill all processes on a port (non-interactive)."""
    from rich.console import Console

    from portkill.services.process_manager import ProcessManager

    console = Console()
    manager = ProcessManager()

    results = manager.kill_by_port(port, force=force)

    if not results:
        console.print(f"[yellow]No processes found on port {port}[/yellow]")
        return 1

    success_count = 0
    for proc, success, error in results:
        if success:
            console.print(
                f"[green]✓[/green] Killed {proc.name} (PID: {proc.pid})"
            )
            success_count += 1
        else:
            console.print(
                f"[red]✗[/red] Failed to kill {proc.name} (PID: {proc.pid}): {error}"
            )

    if success_count == len(results):
        console.print(f"\n[green]All {success_count} process(es) killed.[/green]")
        return 0
    else:
        console.print(
            f"\n[yellow]Killed {success_count}/{len(results)} process(es).[/yellow]"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
