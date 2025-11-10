"""Log viewer screen for processes."""

import subprocess
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static, TextArea
from textual.containers import Vertical
from rich.text import Text

from portkill.widgets.custom_header import AsciiHeader


class LogViewerScreen(Screen):
    """Screen for viewing process logs from journalctl."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    DEFAULT_CSS = """
    LogViewerScreen {
        background: #282828;
    }

    #logs-content {
        height: 1fr;
        background: #1d2021;
        padding: 1;
        color: #ebdbb2;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def __init__(self, pid: int, process_name: str, **kwargs):
        super().__init__(**kwargs)
        self.pid = pid
        self.process_name = process_name

    def compose(self) -> ComposeResult:
        yield AsciiHeader()
        yield Static("Loading logs...", id="logs-content")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Load logs on mount."""
        self._refresh_logs()

    def action_refresh(self) -> None:
        """Refresh logs."""
        self._refresh_logs()
        self.notify("Logs refreshed")

    def action_scroll_down(self) -> None:
        """Scroll logs down."""
        pass  # TextArea handles scrolling

    def action_scroll_up(self) -> None:
        """Scroll logs up."""
        pass

    def action_scroll_top(self) -> None:
        """Scroll to top."""
        pass

    def action_scroll_bottom(self) -> None:
        """Scroll to bottom."""
        pass

    def _refresh_logs(self) -> None:
        """Refresh log content."""
        logs_widget = self.query_one("#logs-content", Static)
        stats_bar = self.query_one("#stats-bar", Static)

        logs = []
        source = "none"

        # Try to get logs from journalctl (for systemd units)
        try:
            result = subprocess.run(
                ["journalctl", f"_PID={self.pid}", "-n", "200", "--no-pager", "-o", "short"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                logs = result.stdout.strip().split('\n')
                source = "journalctl"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # If no journalctl logs, try to read from /proc/<pid>/fd/1 and /proc/<pid>/fd/2
        if not logs:
            try:
                # Try to get cmdline for context
                with open(f"/proc/{self.pid}/cmdline", "r") as f:
                    cmdline = f.read().replace('\0', ' ').strip()
                    logs.append(f"Process: {cmdline}")
                    logs.append("")

                # Check if process has stdout/stderr files
                import os
                fd_dir = f"/proc/{self.pid}/fd"
                if os.path.exists(fd_dir):
                    logs.append("File descriptors available:")
                    for fd in os.listdir(fd_dir):
                        try:
                            link = os.readlink(f"{fd_dir}/{fd}")
                            logs.append(f"  fd/{fd} -> {link}")
                        except (OSError, PermissionError):
                            pass
                    source = "proc"
            except (FileNotFoundError, PermissionError):
                logs.append(f"Unable to read logs for PID {self.pid}")
                logs.append("Process may have terminated or requires elevated permissions")

        # Colorize output
        text = Text()
        for line in logs[-200:]:  # Last 200 lines
            line_lower = line.lower()
            if 'error' in line_lower or 'fatal' in line_lower or 'fail' in line_lower:
                text.append(line + "\n", style="#fb4934")
            elif 'warn' in line_lower:
                text.append(line + "\n", style="#fabd2f")
            elif 'info' in line_lower:
                text.append(line + "\n", style="#83a598")
            elif 'debug' in line_lower:
                text.append(line + "\n", style="#665c54")
            else:
                text.append(line + "\n", style="#ebdbb2")

        logs_widget.update(text)

        # Update stats bar
        stats_text = Text()
        stats_text.append(f" Lines: ", style="#a89984")
        stats_text.append(f"{len(logs)}", style="bold #ebdbb2")
        stats_text.append(f"  │  Source: ", style="#a89984")
        stats_text.append(f"{source}", style="#8ec07c")
        stats_bar.update(stats_text)


class SystemdScreen(Screen):
    """Screen for viewing and managing systemd services."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "start_service", "Start"),
        Binding("S", "stop_service", "Stop"),
        Binding("R", "restart_service", "Restart"),
        Binding("l", "view_logs", "Logs"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    DEFAULT_CSS = """
    SystemdScreen {
        background: #282828;
    }

    #services-table {
        height: 1fr;
        background: #282828;
    }

    #services-table > .datatable--header {
        background: #3c3836;
        color: #8ec07c;
        text-style: bold;
    }

    #services-table > .datatable--cursor {
        background: #504945;
    }

    #services-table:focus > .datatable--cursor {
        background: #d3869b;
        color: #282828;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        from textual.widgets import DataTable
        yield AsciiHeader()
        yield DataTable(id="services-table")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table."""
        from textual.widgets import DataTable
        table = self.query_one("#services-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        table.add_column("Unit", width=35)
        table.add_column("Load", width=10)
        table.add_column("Active", width=10)
        table.add_column("Sub", width=12)
        table.add_column("Description", width=40)

        self._refresh_services()

    def action_refresh(self) -> None:
        """Refresh services."""
        self._refresh_services()
        self.notify("Services refreshed")

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        from textual.widgets import DataTable
        table = self.query_one("#services-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        from textual.widgets import DataTable
        table = self.query_one("#services-table", DataTable)
        table.action_cursor_up()

    def action_start_service(self) -> None:
        """Start selected service."""
        service = self._get_selected_service()
        if not service:
            self.notify("No service selected", severity="warning")
            return

        self._run_systemctl("start", service)

    def action_stop_service(self) -> None:
        """Stop selected service."""
        service = self._get_selected_service()
        if not service:
            self.notify("No service selected", severity="warning")
            return

        self._run_systemctl("stop", service)

    def action_restart_service(self) -> None:
        """Restart selected service."""
        service = self._get_selected_service()
        if not service:
            self.notify("No service selected", severity="warning")
            return

        self._run_systemctl("restart", service)

    def action_view_logs(self) -> None:
        """View service logs."""
        service = self._get_selected_service()
        if not service:
            self.notify("No service selected", severity="warning")
            return

        self.app.push_screen(SystemdLogsScreen(service))

    def _get_selected_service(self) -> str | None:
        """Get selected service name."""
        from textual.widgets import DataTable
        table = self.query_one("#services-table", DataTable)
        if table.cursor_row is None:
            return None

        services = self._get_services()
        if table.cursor_row < len(services):
            return services[table.cursor_row].get("unit")
        return None

    def _run_systemctl(self, action: str, service: str) -> None:
        """Run systemctl command."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", action, service],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.notify(f"{action.capitalize()}ed {service}", severity="information")
                self._refresh_services()
            else:
                # Try with sudo hint
                self.notify(f"Failed: may need sudo. {result.stderr[:50]}", severity="warning")
        except subprocess.TimeoutExpired:
            self.notify("Timeout", severity="error")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def _get_services(self) -> list[dict]:
        """Get list of systemd services."""
        services = []

        try:
            # Get user services first
            result = subprocess.run(
                ["systemctl", "--user", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
                capture_output=True,
                text=True,
                timeout=10
            )

            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        services.append({
                            "unit": parts[0],
                            "load": parts[1],
                            "active": parts[2],
                            "sub": parts[3],
                            "description": parts[4] if len(parts) > 4 else "",
                        })

            # Also get relevant system services (dev-related)
            dev_services = ["docker", "postgresql", "mysql", "redis", "nginx", "apache", "mongodb"]
            for svc in dev_services:
                try:
                    check = subprocess.run(
                        ["systemctl", "is-active", f"{svc}.service"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    status = check.stdout.strip()
                    if status in ["active", "inactive", "failed"]:
                        services.append({
                            "unit": f"{svc}.service",
                            "load": "loaded",
                            "active": status,
                            "sub": "running" if status == "active" else "dead",
                            "description": f"{svc.capitalize()} service",
                        })
                except:
                    pass

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return services

    def _refresh_services(self) -> None:
        """Refresh service list."""
        from textual.widgets import DataTable
        table = self.query_one("#services-table", DataTable)
        table.clear()

        services = self._get_services()

        if not services:
            stats_bar = self.query_one("#stats-bar", Static)
            stats_bar.update(Text(" No systemd services found or systemd not available", style="#fb4934"))
            return

        active = 0
        inactive = 0

        for svc in services:
            is_active = svc["active"] == "active"
            if is_active:
                active += 1
            else:
                inactive += 1

            table.add_row(
                Text(svc["unit"][:34], style="bold #ebdbb2"),
                self._format_load(svc["load"]),
                self._format_active(svc["active"]),
                Text(svc["sub"][:11], style="#a89984"),
                Text(svc["description"][:39], style="#665c54"),
            )

        # Update stats bar
        stats_bar = self.query_one("#stats-bar", Static)
        stats_text = Text()
        stats_text.append(f" Services: ", style="#a89984")
        stats_text.append(f"{len(services)}", style="bold #ebdbb2")
        stats_text.append(f"  │  Active: ", style="#a89984")
        stats_text.append(f"{active}", style="#b8bb26")
        stats_text.append(f"  Inactive: ", style="#a89984")
        stats_text.append(f"{inactive}", style="#665c54")
        stats_bar.update(stats_text)

    def _format_load(self, load: str) -> Text:
        """Format load state."""
        if load == "loaded":
            return Text(load, style="#b8bb26")
        elif load == "not-found":
            return Text(load, style="#fb4934")
        return Text(load, style="#a89984")

    def _format_active(self, active: str) -> Text:
        """Format active state."""
        if active == "active":
            return Text(f"● {active}", style="#b8bb26")
        elif active == "failed":
            return Text(f"✗ {active}", style="#fb4934")
        return Text(f"○ {active}", style="#665c54")


class SystemdLogsScreen(Screen):
    """Screen for viewing systemd service logs."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    SystemdLogsScreen {
        background: #282828;
    }

    #logs {
        height: 1fr;
        background: #1d2021;
        padding: 1;
        color: #ebdbb2;
    }
    """

    def __init__(self, service: str, **kwargs):
        super().__init__(**kwargs)
        self.service = service

    def compose(self) -> ComposeResult:
        yield AsciiHeader()
        yield Static("Loading logs...", id="logs")
        yield Footer()

    def on_mount(self) -> None:
        """Load logs."""
        self._refresh_logs()

    def action_refresh(self) -> None:
        """Refresh logs."""
        self._refresh_logs()
        self.notify("Logs refreshed")

    def _refresh_logs(self) -> None:
        """Refresh log content."""
        logs_widget = self.query_one("#logs", Static)

        try:
            result = subprocess.run(
                ["journalctl", "-u", self.service, "-n", "200", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=10
            )

            output = result.stdout + result.stderr
            if output:
                text = Text()
                for line in output.split('\n')[-200:]:
                    line_lower = line.lower()
                    if 'error' in line_lower or 'fatal' in line_lower:
                        text.append(line + "\n", style="#fb4934")
                    elif 'warn' in line_lower:
                        text.append(line + "\n", style="#fabd2f")
                    elif 'info' in line_lower:
                        text.append(line + "\n", style="#83a598")
                    else:
                        text.append(line + "\n", style="#ebdbb2")
                logs_widget.update(text)
            else:
                logs_widget.update("No logs available")

        except subprocess.TimeoutExpired:
            logs_widget.update("Timeout fetching logs")
        except Exception as e:
            logs_widget.update(f"Error: {e}")
