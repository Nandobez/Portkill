"""Connection graph visualization screen."""

import psutil
from collections import defaultdict
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static
from textual.containers import VerticalScroll
from rich.text import Text

from portkill.widgets.custom_header import AsciiHeader


class ConnectionGraphScreen(Screen):
    """Screen showing network connection graph."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("l", "toggle_local", "Toggle Local"),
        Binding("e", "toggle_established", "Established Only"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    DEFAULT_CSS = """
    ConnectionGraphScreen {
        background: #282828;
    }

    #graph-scroll {
        height: 1fr;
        width: 100%;
        background: #282828;
    }

    #graph-content {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._show_local = True
        self._established_only = False

    def compose(self) -> ComposeResult:
        yield AsciiHeader()
        with VerticalScroll(id="graph-scroll"):
            yield Static("Loading...", id="graph-content")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Load graph on mount."""
        self._refresh_graph()

    def action_refresh(self) -> None:
        """Refresh graph."""
        self._refresh_graph()
        self.notify("Graph refreshed")

    def action_toggle_local(self) -> None:
        """Toggle showing local connections."""
        self._show_local = not self._show_local
        self._refresh_graph()
        status = "shown" if self._show_local else "hidden"
        self.notify(f"Local connections {status}")

    def action_toggle_established(self) -> None:
        """Toggle showing only established connections."""
        self._established_only = not self._established_only
        self._refresh_graph()
        status = "only" if self._established_only else "all"
        self.notify(f"Showing {status} connections")

    def action_scroll_down(self) -> None:
        """Scroll down."""
        scroll = self.query_one("#graph-scroll", VerticalScroll)
        scroll.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up."""
        scroll = self.query_one("#graph-scroll", VerticalScroll)
        scroll.scroll_up()

    def action_scroll_top(self) -> None:
        """Scroll to top."""
        scroll = self.query_one("#graph-scroll", VerticalScroll)
        scroll.scroll_home()

    def action_scroll_bottom(self) -> None:
        """Scroll to bottom."""
        scroll = self.query_one("#graph-scroll", VerticalScroll)
        scroll.scroll_end()

    def _refresh_graph(self) -> None:
        """Refresh connection graph."""
        content = self.query_one("#graph-content", Static)
        stats_bar = self.query_one("#stats-bar", Static)

        # Collect connection data
        connections = []
        processes = {}
        remote_hosts = defaultdict(list)

        access_denied = False
        try:
            for conn in psutil.net_connections(kind="inet"):
                if not conn.laddr:
                    continue

                # Filter by status
                if self._established_only and conn.status != "ESTABLISHED":
                    continue

                # Skip local-only if toggled off
                if not self._show_local:
                    if conn.raddr and conn.raddr.ip in ("127.0.0.1", "::1", "0.0.0.0"):
                        continue

                # Get process info
                proc_name = "unknown"
                if conn.pid:
                    if conn.pid not in processes:
                        try:
                            proc = psutil.Process(conn.pid)
                            processes[conn.pid] = proc.name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            processes[conn.pid] = "?"
                    proc_name = processes.get(conn.pid, "?")

                local_addr = f"{conn.laddr.ip}:{conn.laddr.port}"
                remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "*:*"

                conn_data = {
                    "pid": conn.pid,
                    "process": proc_name,
                    "local": local_addr,
                    "remote": remote_addr,
                    "status": conn.status if hasattr(conn, "status") else "?",
                    "type": "TCP" if conn.type == 1 else "UDP",
                }
                connections.append(conn_data)

                # Group by remote host
                if conn.raddr:
                    remote_hosts[conn.raddr.ip].append(conn_data)

        except psutil.AccessDenied:
            access_denied = True

        # Build graph visualization
        text = Text()

        # Show warning if access denied
        if access_denied:
            text.append("⚠ Access Denied - run with sudo for full visibility\n\n", style="bold #fb4934")

        # Show message if no connections
        if not connections:
            text.append("No connections found.\n", style="#a89984")
            text.append("Try: ", style="#665c54")
            text.append("l", style="bold #8ec07c")
            text.append(" toggle local  ", style="#665c54")
            text.append("e", style="bold #8ec07c")
            text.append(" toggle established only\n\n", style="#665c54")

        # === Process-centric view ===
        text.append("═══ Process Connection Map ═══\n\n", style="bold #fe8019")

        # Group connections by process
        by_process = defaultdict(list)
        for conn in connections:
            by_process[conn["process"]].append(conn)

        # Show top processes
        sorted_procs = sorted(by_process.items(), key=lambda x: -len(x[1]))[:10]

        for proc_name, proc_conns in sorted_procs:
            # Process node
            text.append("  ┌─ ", style="#504945")
            text.append(f"● {proc_name}", style="bold #fabd2f")
            text.append(f" ({len(proc_conns)} conn)\n", style="#a89984")

            # Group by status
            by_status = defaultdict(list)
            for c in proc_conns:
                by_status[c["status"]].append(c)

            for status, status_conns in sorted(by_status.items()):
                status_color = self._status_color(status)
                text.append("  │  ├─ ", style="#504945")
                text.append(f"{status}", style=status_color)
                text.append(f" ({len(status_conns)})\n", style="#665c54")

                # Show up to 3 connections per status
                for i, c in enumerate(status_conns[:3]):
                    is_last = i == min(2, len(status_conns) - 1)
                    prefix = "└─" if is_last else "├─"

                    text.append(f"  │  │  {prefix} ", style="#504945")
                    text.append(f":{c['local'].split(':')[-1]}", style="#b8bb26")
                    text.append(" ──▶ ", style="#665c54")

                    if c["remote"] == "*:*":
                        text.append("*:*", style="#665c54")
                    else:
                        remote_ip = c["remote"].split(":")[0]
                        remote_port = c["remote"].split(":")[-1]
                        text.append(f"{remote_ip}", style="#83a598")
                        text.append(f":{remote_port}", style="#8ec07c")
                    text.append("\n")

                if len(status_conns) > 3:
                    text.append(f"  │  │     ... +{len(status_conns) - 3} more\n", style="#665c54")

            text.append("  │\n", style="#504945")

        text.append("\n")

        # === Remote Host View ===
        text.append("═══ Remote Hosts ═══\n\n", style="bold #83a598")

        # Filter and sort remote hosts
        external_hosts = {
            ip: conns for ip, conns in remote_hosts.items()
            if ip not in ("127.0.0.1", "::1", "0.0.0.0", "")
        }

        sorted_hosts = sorted(external_hosts.items(), key=lambda x: -len(x[1]))[:10]

        if sorted_hosts:
            for host_ip, host_conns in sorted_hosts:
                conn_count = len(host_conns)

                # Determine host "heat"
                if conn_count >= 10:
                    heat_color = "#fb4934"
                    heat_icon = "█"
                elif conn_count >= 5:
                    heat_color = "#fe8019"
                    heat_icon = "▓"
                elif conn_count >= 2:
                    heat_color = "#fabd2f"
                    heat_icon = "▒"
                else:
                    heat_color = "#b8bb26"
                    heat_icon = "░"

                text.append(f"  {heat_icon} ", style=heat_color)
                text.append(f"{host_ip:40}", style="#ebdbb2")
                text.append(f" ← {conn_count:3} connections\n", style="#a89984")

                # Show processes connecting to this host
                procs_to_host = set(c["process"] for c in host_conns)
                text.append("    └─ ", style="#504945")
                text.append(", ".join(list(procs_to_host)[:4]), style="#665c54")
                if len(procs_to_host) > 4:
                    text.append(f" +{len(procs_to_host)-4}", style="#665c54")
                text.append("\n")

        else:
            text.append("  No external connections\n", style="#665c54")

        text.append("\n")

        # === Connection Flow Diagram ===
        text.append("═══ Connection Flow ═══\n\n", style="bold #d3869b")

        # Simple ASCII flow diagram
        listen_count = sum(1 for c in connections if c["status"] == "LISTEN")
        established_count = sum(1 for c in connections if c["status"] == "ESTABLISHED")
        time_wait_count = sum(1 for c in connections if c["status"] == "TIME_WAIT")
        other_count = len(connections) - listen_count - established_count - time_wait_count

        text.append("                  ┌───────────────┐\n", style="#504945")
        text.append("                  │   ", style="#504945")
        text.append("THIS HOST", style="bold #ebdbb2")
        text.append("   │\n", style="#504945")
        text.append("                  └───────┬───────┘\n", style="#504945")
        text.append("                          │\n", style="#504945")
        text.append("        ┌─────────────────┼─────────────────┐\n", style="#504945")
        text.append("        │                 │                 │\n", style="#504945")
        text.append("        ▼                 ▼                 ▼\n", style="#504945")

        text.append("  ┌───────────┐     ┌───────────┐     ┌───────────┐\n", style="#504945")

        text.append("  │  ", style="#504945")
        text.append("LISTEN", style="#fabd2f")
        text.append("   │     │  ", style="#504945")
        text.append("ACTIVE", style="#b8bb26")
        text.append("   │     │  ", style="#504945")
        text.append("OTHER", style="#a89984")
        text.append("    │\n", style="#504945")

        text.append("  │  ", style="#504945")
        text.append(f"{listen_count:^7}", style="bold #fabd2f")
        text.append("  │     │  ", style="#504945")
        text.append(f"{established_count:^7}", style="bold #b8bb26")
        text.append("  │     │  ", style="#504945")
        text.append(f"{other_count:^7}", style="bold #a89984")
        text.append("  │\n", style="#504945")

        text.append("  └───────────┘     └───────────┘     └───────────┘\n", style="#504945")

        if time_wait_count > 0:
            text.append(f"\n  TIME_WAIT: {time_wait_count}\n", style="#665c54")

        text.append("\n")

        # === Protocol breakdown ===
        tcp_count = sum(1 for c in connections if c["type"] == "TCP")
        udp_count = sum(1 for c in connections if c["type"] == "UDP")

        text.append("  Protocol: ", style="#a89984")
        text.append(f"TCP ", style="#83a598")
        text.append(f"{tcp_count}", style="bold #83a598")
        text.append("  │  ", style="#504945")
        text.append(f"UDP ", style="#d3869b")
        text.append(f"{udp_count}", style="bold #d3869b")
        text.append("\n")

        content.update(text)

        # Stats bar
        stats_text = Text()
        stats_text.append(f" Total: ", style="#a89984")
        stats_text.append(f"{len(connections)}", style="bold #ebdbb2")
        stats_text.append(f"  │  Processes: ", style="#a89984")
        stats_text.append(f"{len(by_process)}", style="bold #fabd2f")
        stats_text.append(f"  │  Remote hosts: ", style="#a89984")
        stats_text.append(f"{len(external_hosts)}", style="bold #83a598")

        filters = []
        if not self._show_local:
            filters.append("no-local")
        if self._established_only:
            filters.append("established")
        if filters:
            stats_text.append(f"  │  Filters: ", style="#a89984")
            stats_text.append(", ".join(filters), style="#fe8019")

        stats_bar.update(stats_text)

    def _status_color(self, status: str) -> str:
        """Get color for connection status."""
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
        return colors.get(status, "#665c54")
