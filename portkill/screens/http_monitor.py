"""HTTP Request Monitor screen."""

import socket
import ssl
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from collections import deque
from typing import Optional

import psutil
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static, DataTable
from rich.text import Text

from portkill.widgets.custom_header import AsciiHeader


@dataclass
class HttpConnection:
    """Represents an HTTP connection."""
    timestamp: datetime
    pid: int
    process: str
    local_addr: str
    remote_addr: str
    remote_host: str
    port: int
    protocol: str  # HTTP or HTTPS
    status: str


class HttpMonitorScreen(Screen):
    """Screen for monitoring HTTP/HTTPS connections."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "clear", "Clear"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    DEFAULT_CSS = """
    HttpMonitorScreen {
        background: #282828;
    }

    #control-bar {
        height: 3;
        background: #3c3836;
        padding: 1 2;
        border-bottom: solid #504945;
    }

    #control-bar Horizontal {
        height: 1;
        align: left middle;
    }

    #control-bar .label {
        width: auto;
        color: #a89984;
        padding: 0 1 0 0;
    }

    #control-bar .label-highlight {
        width: auto;
        color: #83a598;
        text-style: bold;
        padding: 0 1 0 0;
    }

    #control-bar .separator {
        width: auto;
        color: #504945;
        padding: 0 2;
    }

    #control-bar .shortcut {
        width: auto;
        color: #8ec07c;
        text-style: bold;
        padding: 0;
    }

    #control-bar .shortcut-desc {
        width: auto;
        color: #a89984;
        padding: 0 2 0 0;
    }

    #control-bar .status-on {
        width: auto;
        color: #b8bb26;
        text-style: bold;
        padding: 0 1;
    }

    #control-bar .status-off {
        width: auto;
        color: #fb4934;
        text-style: bold;
        padding: 0 1;
    }

    #http-table {
        height: 1fr;
        background: #282828;
    }

    #http-table > .datatable--header {
        background: #3c3836;
        color: #8ec07c;
        text-style: bold;
    }

    #http-table > .datatable--cursor {
        background: #504945;
    }

    #http-table:focus > .datatable--cursor {
        background: #83a598;
        color: #282828;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connections: deque[HttpConnection] = deque(maxlen=500)
        self._seen_connections: set[str] = set()
        self._paused = False
        self._monitoring = True
        self._http_ports = {80, 8080, 8000, 3000, 5000, 8888, 4200, 5173, 3001}
        self._https_ports = {443, 8443, 9443}
        self._stats = {"http": 0, "https": 0, "total": 0}

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal

        yield AsciiHeader()

        with Horizontal(id="control-bar"):
            yield Static("HTTP Monitor", classes="label-highlight")
            yield Static("│", classes="separator")
            yield Static("r", classes="shortcut")
            yield Static(":refresh", classes="shortcut-desc")
            yield Static("c", classes="shortcut")
            yield Static(":clear", classes="shortcut-desc")
            yield Static("p", classes="shortcut")
            yield Static(":pause", classes="shortcut-desc")
            yield Static("│", classes="separator")
            yield Static("Ports:", classes="label")
            yield Static("80,443,3000,5000,8080...", classes="label")

        yield DataTable(id="http-table")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table and start monitoring."""
        table = self.query_one("#http-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        table.add_column("Time", width=10)
        table.add_column("PID", width=8)
        table.add_column("Process", width=18)
        table.add_column("Protocol", width=8)
        table.add_column("Local", width=22)
        table.add_column("Remote Host", width=30)
        table.add_column("Port", width=6)
        table.add_column("Status", width=12)

        self._start_monitoring()

    def _start_monitoring(self) -> None:
        """Start the monitoring worker."""
        self._monitor_thread = threading.Thread(target=self._monitor_connections, daemon=True)
        self._monitor_thread.start()

    def _monitor_connections(self) -> None:
        """Monitor HTTP/HTTPS connections in background."""
        while self._monitoring:
            if not self._paused:
                try:
                    self._scan_connections()
                except Exception:
                    pass
            time.sleep(1)

    def _scan_connections(self) -> None:
        """Scan for HTTP/HTTPS connections."""
        try:
            connections = psutil.net_connections(kind="inet")

            for conn in connections:
                if conn.status != "ESTABLISHED":
                    continue

                if not conn.raddr:
                    continue

                remote_port = conn.raddr.port

                # Check if it's an HTTP/HTTPS port
                is_http = remote_port in self._http_ports or conn.laddr.port in self._http_ports
                is_https = remote_port in self._https_ports or conn.laddr.port in self._https_ports

                if not (is_http or is_https):
                    # Also check common HTTP ports
                    if remote_port not in range(80, 9999) and conn.laddr.port not in range(80, 9999):
                        continue

                # Create connection key to avoid duplicates
                conn_key = f"{conn.laddr}:{conn.raddr}"
                if conn_key in self._seen_connections:
                    continue

                self._seen_connections.add(conn_key)

                # Get process info
                proc_name = "unknown"
                if conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        proc_name = proc.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # Try to resolve hostname
                remote_host = conn.raddr.ip
                try:
                    host_info = socket.gethostbyaddr(conn.raddr.ip)
                    remote_host = host_info[0][:28]
                except (socket.herror, socket.gaierror):
                    pass

                # Determine protocol
                if is_https or remote_port == 443:
                    protocol = "HTTPS"
                    self._stats["https"] += 1
                else:
                    protocol = "HTTP"
                    self._stats["http"] += 1

                self._stats["total"] += 1

                http_conn = HttpConnection(
                    timestamp=datetime.now(),
                    pid=conn.pid or 0,
                    process=proc_name,
                    local_addr=f"{conn.laddr.ip}:{conn.laddr.port}",
                    remote_addr=f"{conn.raddr.ip}:{conn.raddr.port}",
                    remote_host=remote_host,
                    port=remote_port,
                    protocol=protocol,
                    status="ESTABLISHED"
                )

                self._connections.appendleft(http_conn)

                # Update UI from main thread
                self.app.call_from_thread(self._add_connection_row, http_conn)
                self.app.call_from_thread(self._update_stats)

        except psutil.AccessDenied:
            pass

    def _add_connection_row(self, conn: HttpConnection) -> None:
        """Add a connection row to the table."""
        table = self.query_one("#http-table", DataTable)

        # Protocol styling
        if conn.protocol == "HTTPS":
            proto_text = Text("HTTPS", style="bold #b8bb26")
        else:
            proto_text = Text("HTTP", style="#83a598")

        table.add_row(
            Text(conn.timestamp.strftime("%H:%M:%S"), style="#a89984"),
            Text(str(conn.pid), style="#fabd2f"),
            Text(conn.process[:17], style="#ebdbb2"),
            proto_text,
            Text(conn.local_addr, style="#665c54"),
            Text(conn.remote_host[:29], style="#8ec07c"),
            Text(str(conn.port), style="#fe8019"),
            Text(conn.status, style="#b8bb26"),
        )

    def _update_stats(self) -> None:
        """Update the stats bar."""
        stats_bar = self.query_one("#stats-bar", Static)

        text = Text()
        text.append(" HTTP Connections: ", style="#a89984")
        text.append(f"{self._stats['http']}", style="#83a598")
        text.append("  |  HTTPS: ", style="#a89984")
        text.append(f"{self._stats['https']}", style="#b8bb26")
        text.append("  |  Total: ", style="#a89984")
        text.append(f"{self._stats['total']}", style="bold #ebdbb2")

        if self._paused:
            text.append("  |  ", style="#a89984")
            text.append("PAUSED", style="bold #fb4934")
        else:
            text.append("  |  ", style="#a89984")
            text.append("MONITORING", style="bold #b8bb26")

        stats_bar.update(text)

    def action_refresh(self) -> None:
        """Refresh connections."""
        self._seen_connections.clear()
        self.notify("Monitoring refreshed")

    def action_clear(self) -> None:
        """Clear the connection list."""
        table = self.query_one("#http-table", DataTable)
        table.clear()
        self._connections.clear()
        self._seen_connections.clear()
        self._stats = {"http": 0, "https": 0, "total": 0}
        self._update_stats()
        self.notify("Connections cleared")

    def action_toggle_pause(self) -> None:
        """Toggle pause state."""
        self._paused = not self._paused
        self._update_stats()
        status = "paused" if self._paused else "resumed"
        self.notify(f"Monitoring {status}")

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one("#http-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one("#http-table", DataTable)
        table.action_cursor_up()

    def on_unmount(self) -> None:
        """Stop monitoring when leaving screen."""
        self._monitoring = False
