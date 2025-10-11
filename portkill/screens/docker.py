"""Docker containers screen."""

import subprocess
import json
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static, DataTable
from rich.text import Text

from portkill.widgets.custom_header import AsciiHeader


class DockerScreen(Screen):
    """Screen showing Docker containers and their ports."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "stop_container", "Stop"),
        Binding("S", "start_container", "Start"),
        Binding("l", "view_logs", "Logs"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    DEFAULT_CSS = """
    DockerScreen {
        background: #282828;
    }

    #docker-table {
        height: 1fr;
        background: #282828;
    }

    #docker-table > .datatable--header {
        background: #3c3836;
        color: #8ec07c;
        text-style: bold;
    }

    #docker-table > .datatable--cursor {
        background: #504945;
    }

    #docker-table:focus > .datatable--cursor {
        background: #83a598;
        color: #282828;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }

    #no-docker {
        padding: 2;
        text-align: center;
        color: #fb4934;
    }
    """

    def compose(self) -> ComposeResult:
        yield AsciiHeader()
        yield DataTable(id="docker-table")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table."""
        table = self.query_one("#docker-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("Name", width=25)
        table.add_column("Image", width=30)
        table.add_column("Status", width=15)
        table.add_column("Ports", width=30)
        table.add_column("ID", width=14)

        self._refresh_containers()

    def action_refresh(self) -> None:
        """Refresh containers."""
        self._refresh_containers()
        self.notify("Docker containers refreshed")

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one("#docker-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one("#docker-table", DataTable)
        table.action_cursor_up()

    def action_stop_container(self) -> None:
        """Stop selected container."""
        container = self._get_selected_container()
        if not container:
            self.notify("No container selected", severity="warning")
            return

        try:
            subprocess.run(
                ["docker", "stop", container["id"]],
                capture_output=True,
                timeout=30
            )
            self.notify(f"Stopped {container['name']}", severity="information")
            self._refresh_containers()
        except subprocess.TimeoutExpired:
            self.notify("Timeout stopping container", severity="error")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_start_container(self) -> None:
        """Start selected container."""
        container = self._get_selected_container()
        if not container:
            self.notify("No container selected", severity="warning")
            return

        try:
            subprocess.run(
                ["docker", "start", container["id"]],
                capture_output=True,
                timeout=30
            )
            self.notify(f"Started {container['name']}", severity="information")
            self._refresh_containers()
        except subprocess.TimeoutExpired:
            self.notify("Timeout starting container", severity="error")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_view_logs(self) -> None:
        """View container logs."""
        container = self._get_selected_container()
        if not container:
            self.notify("No container selected", severity="warning")
            return

        # Push logs screen
        self.app.push_screen(DockerLogsScreen(container["id"], container["name"]))

    def _get_selected_container(self) -> dict | None:
        """Get the selected container data."""
        table = self.query_one("#docker-table", DataTable)
        if table.cursor_row is None:
            return None

        # Get containers list
        containers = self._get_containers()
        if table.cursor_row < len(containers):
            return containers[table.cursor_row]
        return None

    def _get_containers(self) -> list[dict]:
        """Get list of Docker containers."""
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return []

            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        containers.append({
                            "id": data.get("ID", ""),
                            "name": data.get("Names", ""),
                            "image": data.get("Image", ""),
                            "status": data.get("Status", ""),
                            "ports": data.get("Ports", ""),
                            "state": data.get("State", ""),
                        })
                    except json.JSONDecodeError:
                        continue

            return containers

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def _refresh_containers(self) -> None:
        """Refresh container list."""
        table = self.query_one("#docker-table", DataTable)
        table.clear()

        containers = self._get_containers()

        if not containers:
            stats_bar = self.query_one("#stats-bar", Static)
            stats_bar.update(Text(" Docker not available or no containers", style="#fb4934"))
            return

        running = 0
        stopped = 0

        for container in containers:
            state = container.get("state", "").lower()
            is_running = state == "running"

            if is_running:
                running += 1
            else:
                stopped += 1

            table.add_row(
                Text(container["name"][:24], style="bold #ebdbb2"),
                Text(container["image"][:29], style="#a89984"),
                self._format_status(container["status"], is_running),
                self._format_ports(container["ports"]),
                Text(container["id"][:12], style="#665c54"),
            )

        # Update stats bar
        stats_bar = self.query_one("#stats-bar", Static)
        stats_text = Text()
        stats_text.append(f" Containers: ", style="#a89984")
        stats_text.append(f"{len(containers)}", style="bold #ebdbb2")
        stats_text.append(f"  │  Running: ", style="#a89984")
        stats_text.append(f"{running}", style="#b8bb26")
        stats_text.append(f"  Stopped: ", style="#a89984")
        stats_text.append(f"{stopped}", style="#fb4934")
        stats_bar.update(stats_text)

    def _format_status(self, status: str, is_running: bool) -> Text:
        """Format container status."""
        if is_running:
            return Text(f"● {status[:13]}", style="#b8bb26")
        return Text(f"○ {status[:13]}", style="#fb4934")

    def _format_ports(self, ports: str) -> Text:
        """Format container ports."""
        if not ports:
            return Text("—", style="#665c54")

        # Parse and format ports nicely
        parts = ports.split(", ")
        if len(parts) > 2:
            return Text(f"{parts[0]}, +{len(parts)-1} more", style="#fabd2f")
        return Text(ports[:29], style="#fabd2f")


class DockerLogsScreen(Screen):
    """Screen showing Docker container logs."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("f", "follow", "Follow"),
    ]

    DEFAULT_CSS = """
    DockerLogsScreen {
        background: #282828;
    }

    #logs {
        height: 1fr;
        background: #1d2021;
        padding: 1;
        overflow-y: auto;
        color: #ebdbb2;
    }
    """

    def __init__(self, container_id: str, container_name: str, **kwargs):
        super().__init__(**kwargs)
        self.container_id = container_id
        self.container_name = container_name

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

    def action_follow(self) -> None:
        """Follow logs (TODO: implement real-time following)."""
        self.notify("Follow mode not yet implemented")

    def _refresh_logs(self) -> None:
        """Refresh container logs."""
        logs_widget = self.query_one("#logs", Static)

        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", "100", self.container_id],
                capture_output=True,
                text=True,
                timeout=10
            )

            output = result.stdout + result.stderr
            if output:
                # Colorize log output
                lines = []
                for line in output.split('\n')[-100:]:
                    if 'error' in line.lower() or 'err' in line.lower():
                        lines.append(f"[#fb4934]{line}[/]")
                    elif 'warn' in line.lower():
                        lines.append(f"[#fabd2f]{line}[/]")
                    elif 'info' in line.lower():
                        lines.append(f"[#83a598]{line}[/]")
                    else:
                        lines.append(line)
                logs_widget.update('\n'.join(lines))
            else:
                logs_widget.update("No logs available")

        except subprocess.TimeoutExpired:
            logs_widget.update("Timeout fetching logs")
        except Exception as e:
            logs_widget.update(f"Error: {e}")
