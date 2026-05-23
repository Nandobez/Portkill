"""Network connections screen."""

import psutil
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static, DataTable
from textual.containers import Vertical
from rich.text import Text

from portkill.widgets.custom_header import AsciiHeader


class ConnectionsScreen(Screen):
    """Screen showing all network connections."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    DEFAULT_CSS = """
    ConnectionsScreen {
        background: #282828;
    }

    #connections-table {
        height: 1fr;
        background: #282828;
    }

    #connections-table > .datatable--header {
        background: #3c3836;
        color: #8ec07c;
        text-style: bold;
    }

    #connections-table > .datatable--cursor {
        background: #504945;
    }

    #connections-table:focus > .datatable--cursor {
        background: #fe8019;
        color: #282828;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield AsciiHeader()
        yield DataTable(id="connections-table")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table."""
        table = self.query_one("#connections-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("Proto", width=6)
        table.add_column("Local Address", width=25)
        table.add_column("Remote Address", width=25)
        table.add_column("Status", width=12)
        table.add_column("PID", width=8)
        table.add_column("Process", width=20)

        self._refresh_connections()

    def action_refresh(self) -> None:
        """Refresh connections."""
        self._refresh_connections()
        self.notify("Connections refreshed")

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one("#connections-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one("#connections-table", DataTable)
        table.action_cursor_up()

    def _refresh_connections(self) -> None:
        """Refresh connection data."""
        table = self.query_one("#connections-table", DataTable)
        table.clear()

        connections = []
        stats = {"tcp": 0, "udp": 0, "established": 0, "listen": 0}

        try:
            # Get all connections
            for conn in psutil.net_connections(kind="inet"):
                proto = "TCP" if conn.type == 1 else "UDP"

                # Format addresses
                if conn.laddr:
                    local = f"{conn.laddr.ip}:{conn.laddr.port}"
                else:
                    local = "*:*"

                if conn.raddr:
                    remote = f"{conn.raddr.ip}:{conn.raddr.port}"
                else:
                    remote = "*:*"

                # Get status
                status = conn.status if hasattr(conn, "status") else "NONE"

                # Get process info
                pid = conn.pid if conn.pid else 0
                proc_name = ""
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        proc_name = proc.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        proc_name = "?"

                connections.append({
                    "proto": proto,
                    "local": local,
                    "remote": remote,
                    "status": status,
                    "pid": pid,
                    "process": proc_name,
                })

                # Update stats
                if proto == "TCP":
                    stats["tcp"] += 1
                else:
                    stats["udp"] += 1

                if status == "ESTABLISHED":
                    stats["established"] += 1
                elif status == "LISTEN":
                    stats["listen"] += 1

        except psutil.AccessDenied:
            self.notify("Need elevated permissions for some connections", severity="warning")

        # Sort by status (ESTABLISHED first, then LISTEN, then others)
        status_order = {"ESTABLISHED": 0, "LISTEN": 1, "TIME_WAIT": 2, "CLOSE_WAIT": 3}
        connections.sort(key=lambda c: (status_order.get(c["status"], 99), c["local"]))

        # Add rows to table
        for conn in connections:
            table.add_row(
                self._format_proto(conn["proto"]),
                Text(conn["local"], style="#ebdbb2"),
                Text(conn["remote"], style="#a89984" if conn["remote"] == "*:*" else "#8ec07c"),
                self._format_status(conn["status"]),
                Text(str(conn["pid"]) if conn["pid"] else "—", style="#fabd2f"),
                Text(conn["process"][:20] if conn["process"] else "—", style="#a89984"),
            )

        # Update stats bar
        stats_bar = self.query_one("#stats-bar", Static)
        stats_text = Text()
        stats_text.append(f" Total: ", style="#a89984")
        stats_text.append(f"{len(connections)}", style="bold #ebdbb2")
        stats_text.append(f"  │  TCP: ", style="#a89984")
        stats_text.append(f"{stats['tcp']}", style="#83a598")
        stats_text.append(f"  UDP: ", style="#a89984")
        stats_text.append(f"{stats['udp']}", style="#d3869b")
        stats_text.append(f"  │  Established: ", style="#a89984")
        stats_text.append(f"{stats['established']}", style="#b8bb26")
        stats_text.append(f"  Listening: ", style="#a89984")
        stats_text.append(f"{stats['listen']}", style="#fabd2f")
        stats_bar.update(stats_text)

    def _format_proto(self, proto: str) -> Text:
        """Format protocol."""
        if proto == "TCP":
            return Text(proto, style="#83a598")
        return Text(proto, style="#d3869b")

    def _format_status(self, status: str) -> Text:
        """Format connection status."""
        colors = {
            "ESTABLISHED": "#b8bb26",
            "LISTEN": "#fabd2f",
            "TIME_WAIT": "#665c54",
            "CLOSE_WAIT": "#fe8019",
            "SYN_SENT": "#8ec07c",
            "SYN_RECV": "#8ec07c",
            "FIN_WAIT1": "#a89984",
            "FIN_WAIT2": "#a89984",
            "CLOSING": "#fb4934",
            "LAST_ACK": "#a89984",
            "NONE": "#665c54",
        }
        color = colors.get(status, "#665c54")
        return Text(status, style=color)
