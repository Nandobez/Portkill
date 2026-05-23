"""Port heatmap visualization screen."""

import psutil
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static
from textual.containers import Vertical, Horizontal
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.console import Group

from portkill.widgets.custom_header import AsciiHeader


class PortHeatmapScreen(Screen):
    """Screen showing port usage heatmap."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    PortHeatmapScreen {
        background: #282828;
    }

    #heatmap-content {
        height: 1fr;
        background: #282828;
        padding: 1 2;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield AsciiHeader()
        yield Static("Loading...", id="heatmap-content")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Load heatmap on mount."""
        self._refresh_heatmap()

    def action_refresh(self) -> None:
        """Refresh heatmap."""
        self._refresh_heatmap()
        self.notify("Heatmap refreshed")

    def _refresh_heatmap(self) -> None:
        """Refresh heatmap visualization."""
        content = self.query_one("#heatmap-content", Static)
        stats_bar = self.query_one("#stats-bar", Static)

        # Collect port data
        port_counts = {}
        total_connections = 0

        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr:
                    port = conn.laddr.port
                    port_counts[port] = port_counts.get(port, 0) + 1
                    total_connections += 1
        except psutil.AccessDenied:
            pass

        # Define port ranges
        ranges = [
            ("Well-known", 0, 1023),
            ("Registered", 1024, 49151),
            ("Dynamic", 49152, 65535),
        ]

        # Common port categories
        categories = {
            "Web": [80, 443, 8080, 8443, 3000, 3001, 5000, 8000, 5173],
            "Database": [3306, 5432, 27017, 6379, 5672, 15672],
            "SSH/Remote": [22, 23, 3389, 5900],
            "Mail": [25, 110, 143, 465, 587, 993, 995],
            "Dev Tools": [9000, 9229, 5555, 4200, 4000, 8888],
        }

        # Build heatmap visualization
        text = Text()

        # Port Range Summary
        text.append("═══ Port Range Distribution ═══\n\n", style="bold #fe8019")

        for name, start, end in ranges:
            count = sum(c for p, c in port_counts.items() if start <= p <= end)
            percentage = (count / total_connections * 100) if total_connections > 0 else 0

            # Create bar
            bar_width = 40
            filled = int(bar_width * percentage / 100)

            text.append(f"  {name:12} ", style="#a89984")
            text.append(f"[{start:5}-{end:5}] ", style="#665c54")

            # Color based on usage
            if percentage > 50:
                bar_color = "#fb4934"
            elif percentage > 20:
                bar_color = "#fabd2f"
            else:
                bar_color = "#b8bb26"

            text.append("█" * filled, style=bar_color)
            text.append("░" * (bar_width - filled), style="#504945")
            text.append(f" {count:4} ({percentage:5.1f}%)\n", style="#ebdbb2")

        text.append("\n")

        # Category heatmap
        text.append("═══ Port Categories ═══\n\n", style="bold #8ec07c")

        for category, ports in categories.items():
            active_ports = [(p, port_counts.get(p, 0)) for p in ports if p in port_counts]
            total_cat = sum(c for _, c in active_ports)

            text.append(f"  {category:12} ", style="bold #ebdbb2")

            if active_ports:
                # Show mini heatmap for category
                for port, count in sorted(active_ports, key=lambda x: -x[1])[:5]:
                    intensity = min(count, 10)
                    if intensity >= 7:
                        color = "#fb4934"
                    elif intensity >= 4:
                        color = "#fabd2f"
                    elif intensity >= 1:
                        color = "#b8bb26"
                    else:
                        color = "#504945"

                    text.append(f"[{port}]", style=color)
                    text.append(" ", style="#282828")

                text.append(f" = {total_cat} conn\n", style="#a89984")
            else:
                text.append("(no active ports)\n", style="#665c54")

        text.append("\n")

        # Top ports heatmap grid
        text.append("═══ Top Active Ports ═══\n\n", style="bold #d3869b")

        # Get top 20 ports
        top_ports = sorted(port_counts.items(), key=lambda x: -x[1])[:20]

        if top_ports:
            max_count = max(c for _, c in top_ports)

            # Create grid
            for i, (port, count) in enumerate(top_ports):
                # Heat color
                ratio = count / max_count if max_count > 0 else 0
                if ratio > 0.7:
                    color = "#fb4934"
                    icon = "█"
                elif ratio > 0.4:
                    color = "#fe8019"
                    icon = "▓"
                elif ratio > 0.2:
                    color = "#fabd2f"
                    icon = "▒"
                else:
                    color = "#b8bb26"
                    icon = "░"

                text.append(f"  {icon} ", style=color)
                text.append(f"{port:5}", style=f"bold {color}")
                text.append(f" ({count:3})", style="#a89984")

                if (i + 1) % 4 == 0:
                    text.append("\n")
                else:
                    text.append("  │  ", style="#504945")

            if len(top_ports) % 4 != 0:
                text.append("\n")
        else:
            text.append("  No active ports found\n", style="#665c54")

        text.append("\n")

        # Visual port range map (ASCII art style)
        text.append("═══ Port Density Map (0-65535) ═══\n\n", style="bold #83a598")

        # Create buckets for the entire port range
        bucket_size = 1024
        buckets = [0] * 64  # 64 buckets of 1024 ports each

        for port, count in port_counts.items():
            bucket_idx = min(port // bucket_size, 63)
            buckets[bucket_idx] += count

        max_bucket = max(buckets) if buckets else 1

        # Draw two rows of 32 buckets each
        text.append("  0", style="#665c54")
        text.append(" " * 30, style="#282828")
        text.append("32K", style="#665c54")
        text.append(" " * 28, style="#282828")
        text.append("65K\n", style="#665c54")

        text.append("  ", style="#282828")
        for i, count in enumerate(buckets):
            ratio = count / max_bucket if max_bucket > 0 else 0
            if ratio > 0.7:
                char = "█"
                color = "#fb4934"
            elif ratio > 0.4:
                char = "▓"
                color = "#fe8019"
            elif ratio > 0.2:
                char = "▒"
                color = "#fabd2f"
            elif ratio > 0:
                char = "░"
                color = "#b8bb26"
            else:
                char = "·"
                color = "#504945"

            text.append(char, style=color)

        text.append("\n")

        # Legend
        text.append("\n  Legend: ", style="#a89984")
        text.append("█", style="#fb4934")
        text.append(" High ", style="#665c54")
        text.append("▓", style="#fe8019")
        text.append(" Med-High ", style="#665c54")
        text.append("▒", style="#fabd2f")
        text.append(" Medium ", style="#665c54")
        text.append("░", style="#b8bb26")
        text.append(" Low ", style="#665c54")
        text.append("·", style="#504945")
        text.append(" None\n", style="#665c54")

        content.update(text)

        # Stats bar
        unique_ports = len(port_counts)
        stats_text = Text()
        stats_text.append(f" Total connections: ", style="#a89984")
        stats_text.append(f"{total_connections}", style="bold #ebdbb2")
        stats_text.append(f"  │  Unique ports: ", style="#a89984")
        stats_text.append(f"{unique_ports}", style="bold #b8bb26")
        stats_bar.update(stats_text)
