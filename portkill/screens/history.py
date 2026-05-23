"""History screen for PortKill."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Footer, DataTable, Static
from rich.text import Text

from portkill.models.history import HistoryDB, KillRecord
from portkill.widgets.custom_header import AsciiHeader


class StatsPanel(Static):
    """Panel showing kill statistics."""

    DEFAULT_CSS = """
    StatsPanel {
        height: auto;
        padding: 1;
        border: solid $primary;
        margin-bottom: 1;
    }

    StatsPanel .stat-row {
        height: 1;
    }
    """

    def update_stats(self, stats: dict):
        """Update stats display."""
        text = Text()
        text.append("Kill Statistics\n", style="bold underline")
        text.append(f"Total Kills: {stats['total_kills']}\n")
        text.append(f"Successful: {stats['successful_kills']}")
        text.append(f" ({stats['success_rate']:.1f}%)\n", style="green")
        text.append(f"Today: {stats['kills_today']}\n")

        if stats["kills_by_service"]:
            text.append("\nBy Service:\n", style="bold")
            for service, count in list(stats["kills_by_service"].items())[:5]:
                text.append(f"  {service}: {count}\n")

        if stats["top_ports"]:
            text.append("\nTop Ports:\n", style="bold")
            for port, count in list(stats["top_ports"].items())[:5]:
                text.append(f"  :{port}: {count}\n")

        self.update(text)


class HistoryScreen(Screen):
    """Screen showing kill history and statistics."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    HistoryScreen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto auto 1fr auto;
    }

    #history-container {
        height: 1fr;
        border: solid $primary;
    }

    #stats-panel {
        height: auto;
        max-height: 15;
    }
    """

    def __init__(self, history_db: HistoryDB, **kwargs):
        super().__init__(**kwargs)
        self.history_db = history_db

    def compose(self) -> ComposeResult:
        """Compose the history screen."""
        yield AsciiHeader()

        yield StatsPanel(id="stats-panel")

        with Container(id="history-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=True)

        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event."""
        # Setup table
        table = self.query_one("#history-table", DataTable)
        table.add_columns(
            "Time",
            "PID",
            "Port",
            "Service",
            "Name",
            "Signal",
            "Status",
        )

        self._refresh_data()

    def _refresh_data(self) -> None:
        """Refresh history data."""
        # Update stats
        stats = self.history_db.get_stats()
        stats_panel = self.query_one("#stats-panel", StatsPanel)
        stats_panel.update_stats(stats)

        # Update table
        table = self.query_one("#history-table", DataTable)
        table.clear()

        records = self.history_db.get_history(limit=100)
        for record in records:
            # Format timestamp
            time_str = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")

            # Format status
            if record.success:
                status = Text("✓ Success", style="green")
            else:
                status = Text(f"✗ {record.error_message[:20]}", style="red")

            table.add_row(
                time_str,
                str(record.pid),
                str(record.port),
                record.service_type,
                record.name[:20],
                record.kill_signal,
                status,
            )

    def action_refresh(self) -> None:
        """Refresh data."""
        self._refresh_data()
        self.notify("Refreshed")

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one("#history-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one("#history-table", DataTable)
        table.action_cursor_up()
