"""Main screen for PortKill."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static
from textual.timer import Timer
from rich.text import Text

from portkill.models.process import PortProcess
from portkill.services.process_manager import ProcessManager
from portkill.widgets.process_table import ProcessTable
from portkill.widgets.filter_bar import FilterBar
from portkill.widgets.details_panel import DetailsPanel
from portkill.widgets.custom_header import AsciiHeader
from portkill.screens.confirm_dialog import KillConfirmDialog
from portkill.screens.connections import ConnectionsScreen
from portkill.screens.process_tree import ProcessTreeScreen
from portkill.screens.docker import DockerScreen
from portkill.screens.logs import LogViewerScreen, SystemdScreen
from portkill.screens.heatmap import PortHeatmapScreen
from portkill.screens.graph import ConnectionGraphScreen
from portkill.screens.http_monitor import HttpMonitorScreen
from portkill.screens.port_scanner import PortScannerScreen
from portkill.services.alerts import AlertsService, Alert, AlertLevel
from portkill.utils.constants import ServiceType, ProcessStatus, REFRESH_INTERVALS, SPARKLINE_CHARS


class BottomBar(Static):
    """Bottom bar with stats and system info - single line."""

    DEFAULT_CSS = """
    BottomBar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._process_count = 0
        self._port_count = 0
        self._selected_count = 0
        self._refresh_interval = 2
        self._auto_refresh = True
        self._cpu = 0.0
        self._memory = 0.0
        self._cpu_history: list[float] = []
        self._memory_history: list[float] = []

    def update_stats(
        self,
        process_count: int,
        port_count: int,
        selected_count: int,
        cpu: float,
        memory: float,
        refresh_interval: int,
        auto_refresh: bool,
    ):
        """Update stats."""
        self._process_count = process_count
        self._port_count = port_count
        self._selected_count = selected_count
        self._refresh_interval = refresh_interval
        self._auto_refresh = auto_refresh
        self._cpu = cpu
        self._memory = memory

        # Update history
        self._cpu_history.append(cpu)
        self._memory_history.append(memory)
        self._cpu_history = self._cpu_history[-20:]
        self._memory_history = self._memory_history[-20:]

        self.refresh()

    def _make_sparkline(self, data: list[float], width: int = 12) -> str:
        """Create sparkline string from data."""
        if not data:
            return "─" * width

        max_val = 100
        display_data = data[-width:]
        chars = SPARKLINE_CHARS

        bars = ""
        for val in display_data:
            normalized = min(1.0, val / max_val)
            idx = int(normalized * (len(chars) - 1))
            bars += chars[idx]

        if len(bars) < width:
            bars = "─" * (width - len(bars)) + bars

        return bars

    def render(self) -> Text:
        """Render the bottom bar - single line."""
        text = Text()

        # Process count
        text.append(" ⚡", style="bold #fabd2f")
        text.append(f" {self._process_count}", style="bold #ebdbb2")
        text.append(" procs", style="#a89984")

        # Port count
        text.append("  🔌", style="#b8bb26")
        text.append(f" {self._port_count}", style="bold #b8bb26")
        text.append(" ports", style="#a89984")

        # Selected count
        if self._selected_count > 0:
            text.append("  ✓", style="#fe8019")
            text.append(f" {self._selected_count}", style="bold #fe8019")

        text.append("  │", style="#504945")

        # CPU with mini sparkline
        cpu_spark = self._make_sparkline(self._cpu_history, 12)
        text.append(" CPU ", style="#a89984")
        text.append(cpu_spark, style=self._cpu_color(self._cpu))
        text.append(f" {self._cpu:4.1f}%", style=f"bold {self._cpu_color(self._cpu)}")

        text.append(" │", style="#504945")

        # Memory with mini sparkline
        mem_spark = self._make_sparkline(self._memory_history, 12)
        text.append(" MEM ", style="#a89984")
        text.append(mem_spark, style=self._mem_color(self._memory))
        text.append(f" {self._memory:4.1f}%", style=f"bold {self._mem_color(self._memory)}")

        text.append(" │", style="#504945")

        # Refresh status
        if self._auto_refresh:
            text.append(" ⟳", style="#b8bb26")
            text.append(f" {self._refresh_interval}s", style="#a89984")
        else:
            text.append(" ⏸", style="#fabd2f")
            text.append(" paused", style="#a89984")

        return text

    def _cpu_color(self, cpu: float) -> str:
        """Get color for CPU usage."""
        if cpu > 80:
            return "#fb4934"
        elif cpu > 50:
            return "#fabd2f"
        return "#b8bb26"

    def _mem_color(self, mem: float) -> str:
        """Get color for memory usage."""
        if mem > 80:
            return "#fb4934"
        elif mem > 60:
            return "#fabd2f"
        return "#d3869b"


class MainScreen(Screen):
    """Main screen of PortKill application."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "show_help", "Help"),
        Binding("d", "toggle_details", "Details"),
        Binding("enter", "toggle_details", "Details", show=False),
        Binding("k", "kill_process", "Kill"),
        Binding("K", "force_kill", "Force Kill"),
        Binding("r", "toggle_refresh", "Auto-refresh"),
        Binding("R", "manual_refresh", "Refresh"),
        Binding("h", "show_history", "History"),
        Binding("n", "show_connections", "Network"),
        Binding("t", "show_tree", "Tree"),
        Binding("D", "show_docker", "Docker"),
        Binding("l", "show_logs", "Logs"),
        Binding("s", "show_systemd", "Systemd"),
        Binding("H", "show_heatmap", "Heatmap"),
        Binding("g", "show_graph", "Graph"),
        Binding("m", "show_http_monitor", "HTTP Mon"),
        Binding("p", "show_port_scanner", "Port Scan"),
        Binding("a", "toggle_alerts", "Alerts"),
        Binding("/", "focus_search", "Search"),
        Binding("c", "clear_filters", "Clear"),
        Binding("escape", "clear_selection", "Clear Selection"),
    ]

    DEFAULT_CSS = """
    MainScreen {
        layout: vertical;
        width: 100%;
        background: #282828;
    }

    #header {
        height: auto;
        width: 100%;
        min-height: 8;
        text-align: center;
        border-bottom: solid #fe8019;
    }

    #filter-bar {
        height: 3;
        width: 100%;
    }

    #process-table {
        height: 1fr;
        width: 100%;
        min-width: 100%;
        background: #282828;
    }

    #details-panel {
        height: auto;
        max-height: 10;
        display: none;
    }

    #details-panel.visible {
        display: block;
    }

    #bottom-bar {
        height: 1;
        background: #3c3836;
    }

    Footer {
        background: #3c3836;
    }

    Footer > FooterKey > .footer-key--key {
        background: #fe8019;
        color: #282828;
    }

    Footer > FooterKey > .footer-key--description {
        color: #a89984;
    }
    """

    def __init__(self, process_manager: ProcessManager, **kwargs):
        super().__init__(**kwargs)
        self.process_manager = process_manager
        self._refresh_timer: Timer | None = None
        self._refresh_interval = 2
        self._auto_refresh = True
        self._current_filters: dict = {}
        self._show_all_dev = True  # Default to showing all dev processes
        self._show_details = False  # Details panel visibility
        self._alerts_enabled = True
        self._alerts_service = AlertsService()
        self._alerts_service.on_alert(self._on_alert)

    def compose(self) -> ComposeResult:
        """Compose the main screen."""
        yield AsciiHeader(id="header")
        yield FilterBar(id="filter-bar")
        yield ProcessTable(id="process-table")
        yield DetailsPanel(id="details-panel")
        yield BottomBar(id="bottom-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event."""
        self._refresh_data()
        self._start_refresh_timer()

    def _start_refresh_timer(self) -> None:
        """Start the auto-refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.stop()

        if self._auto_refresh:
            self._refresh_timer = self.set_interval(
                self._refresh_interval, self._refresh_data
            )

    def _on_alert(self, alert: Alert) -> None:
        """Handle new alert."""
        if not self._alerts_enabled:
            return

        severity = "warning" if alert.level == AlertLevel.WARNING else "error"
        if alert.level == AlertLevel.INFO:
            severity = "information"

        self.notify(
            f"{alert.icon} {alert.title}",
            severity=severity,
            timeout=5
        )

    def _refresh_data(self) -> None:
        """Refresh process data."""
        # Get processes based on mode
        if self._show_all_dev:
            # Show all development processes (with and without ports)
            processes = self.process_manager.get_dev_processes(
                service_filter=self._current_filters.get("service_type"),
                status_filter=self._current_filters.get("status"),
                search_query=self._current_filters.get("search"),
                include_ports=True,
            )
        else:
            # Show only processes with ports
            processes = self.process_manager.get_port_processes(
                port_filter=self._current_filters.get("port"),
                port_range=self._current_filters.get("port_range"),
                service_filter=self._current_filters.get("service_type"),
                status_filter=self._current_filters.get("status"),
                protocol_filter=self._current_filters.get("protocol"),
                search_query=self._current_filters.get("search"),
            )

        # Check for alerts
        if self._alerts_enabled:
            for proc in processes:
                self._alerts_service.check_process(
                    proc.pid,
                    proc.name,
                    proc.cpu_percent,
                    proc.memory_mb,
                    proc.connections_count,
                )

        # Update table
        table = self.query_one("#process-table", ProcessTable)
        table.update_processes(processes)

        # Update system stats
        stats = self.process_manager.get_system_stats()

        # Update details panel if visible
        current = table.get_current_process()
        if self._show_details:
            details = self.query_one("#details-panel", DetailsPanel)
            details.update_process(current)

        # Update bottom bar
        bottom_bar = self.query_one("#bottom-bar", BottomBar)
        unique_ports = len(set(p.port for p in processes if p.port > 0))
        selected = len([p for p in processes if p.selected])

        bottom_bar.update_stats(
            process_count=len(processes),
            port_count=unique_ports,
            selected_count=selected,
            cpu=stats["cpu_percent"],
            memory=stats["memory_percent"],
            refresh_interval=self._refresh_interval,
            auto_refresh=self._auto_refresh,
        )

    def on_filter_bar_filters_changed(self, event: FilterBar.FiltersChanged) -> None:
        """Handle filter changes."""
        self._show_all_dev = event.show_all_dev
        self._current_filters = {
            "service_type": event.service_type,
            "status": event.status,
            "protocol": event.protocol,
            "port": event.port,
            "port_range": event.port_range,
            "search": event.search,
        }
        self._refresh_data()

    def on_process_table_process_toggled(
        self, event: ProcessTable.ProcessToggled
    ) -> None:
        """Handle process selection toggle."""
        self.process_manager.toggle_selection(event.pid)
        self._refresh_data()

    def on_process_table_select_all_requested(
        self, event: ProcessTable.SelectAllRequested
    ) -> None:
        """Handle select all request."""
        table = self.query_one("#process-table", ProcessTable)
        processes = table._processes
        self.process_manager.select_all(processes)
        self._refresh_data()

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row highlight change - update details panel."""
        if self._show_details:
            table = self.query_one("#process-table", ProcessTable)
            current = table.get_current_process()
            details = self.query_one("#details-panel", DetailsPanel)
            details.update_process(current)

    def action_kill_process(self) -> None:
        """Kill selected process(es)."""
        self._do_kill(force=False)

    def action_force_kill(self) -> None:
        """Force kill selected process(es)."""
        self._do_kill(force=True)

    def _do_kill(self, force: bool) -> None:
        """Perform kill operation."""
        table = self.query_one("#process-table", ProcessTable)

        # Get processes to kill
        selected = self.process_manager.get_selected_processes()
        if not selected:
            # Kill current if none selected
            current = table.get_current_process()
            if current:
                selected = [current]

        if not selected:
            self.notify("No process selected", severity="warning")
            return

        # Store for callback
        self._pending_kill_processes = selected
        self._pending_kill_force = force

        # Show confirmation dialog
        count = len(selected)
        if count == 1:
            proc = selected[0]
            dialog = KillConfirmDialog(
                process_name=proc.name,
                pid=proc.pid,
                port=proc.port if proc.port > 0 else None,
                count=1,
                force=force,
            )
        else:
            dialog = KillConfirmDialog(
                process_name="multiple",
                pid=0,
                count=count,
                force=force,
            )

        self.app.push_screen(dialog, self._on_kill_confirmed)

    def _on_kill_confirmed(self, confirmed: bool) -> None:
        """Handle kill confirmation result."""
        if not confirmed:
            self.notify("Kill cancelled", severity="information")
            return

        selected = self._pending_kill_processes
        force = self._pending_kill_force

        # Perform kill
        results = self.process_manager.kill_processes(selected, force=force)

        success_count = sum(1 for _, success, _ in results if success)
        fail_count = len(results) - success_count

        if fail_count == 0:
            self.notify(f"Killed {success_count} process(es)", severity="information")
        else:
            self.notify(
                f"Killed {success_count}, failed {fail_count}", severity="warning"
            )

        self._refresh_data()

    def action_toggle_refresh(self) -> None:
        """Toggle auto-refresh."""
        self._auto_refresh = not self._auto_refresh
        self._start_refresh_timer()
        status = "enabled" if self._auto_refresh else "disabled"
        self.notify(f"Auto-refresh {status}")
        self._refresh_data()

    def action_manual_refresh(self) -> None:
        """Manual refresh."""
        self._refresh_data()
        self.notify("Refreshed")

    def action_focus_search(self) -> None:
        """Focus the search input."""
        filter_bar = self.query_one("#filter-bar", FilterBar)
        filter_bar.focus_search()

    def action_clear_filters(self) -> None:
        """Clear all filters."""
        filter_bar = self.query_one("#filter-bar", FilterBar)
        filter_bar.clear_filters()
        self._current_filters = {}
        self._refresh_data()

    def action_clear_selection(self) -> None:
        """Clear all selections."""
        self.process_manager.deselect_all()
        self._refresh_data()

    def action_show_history(self) -> None:
        """Show history screen."""
        from portkill.screens.history import HistoryScreen
        self.app.push_screen(HistoryScreen(self.process_manager.history_db))

    def action_show_connections(self) -> None:
        """Show network connections screen."""
        self.app.push_screen(ConnectionsScreen())

    def action_show_tree(self) -> None:
        """Show process tree screen."""
        # Get current process PID if one is selected
        table = self.query_one("#process-table", ProcessTable)
        current = table.get_current_process()
        root_pid = current.pid if current else None
        self.app.push_screen(ProcessTreeScreen(root_pid=root_pid))

    def action_show_docker(self) -> None:
        """Show Docker containers screen."""
        self.app.push_screen(DockerScreen())

    def action_toggle_alerts(self) -> None:
        """Toggle alerts on/off."""
        self._alerts_enabled = not self._alerts_enabled
        status = "enabled" if self._alerts_enabled else "disabled"
        self.notify(f"Alerts {status}")

    def action_show_logs(self) -> None:
        """Show logs for selected process."""
        table = self.query_one("#process-table", ProcessTable)
        current = table.get_current_process()
        if not current:
            self.notify("No process selected", severity="warning")
            return
        self.app.push_screen(LogViewerScreen(current.pid, current.name))

    def action_show_systemd(self) -> None:
        """Show systemd services screen."""
        self.app.push_screen(SystemdScreen())

    def action_show_heatmap(self) -> None:
        """Show port heatmap screen."""
        self.app.push_screen(PortHeatmapScreen())

    def action_show_graph(self) -> None:
        """Show connection graph screen."""
        self.app.push_screen(ConnectionGraphScreen())

    def action_show_http_monitor(self) -> None:
        """Show HTTP monitor screen."""
        self.app.push_screen(HttpMonitorScreen())

    def action_show_port_scanner(self) -> None:
        """Show port scanner screen."""
        self.app.push_screen(PortScannerScreen())

    def action_toggle_details(self) -> None:
        """Toggle details panel visibility."""
        self._show_details = not self._show_details
        details = self.query_one("#details-panel", DetailsPanel)

        if self._show_details:
            details.add_class("visible")
            # Update with current process
            table = self.query_one("#process-table", ProcessTable)
            current = table.get_current_process()
            details.update_process(current)
        else:
            details.remove_class("visible")

    def action_show_help(self) -> None:
        """Show help dialog."""
        help_text = """
[bold]PortKill - Keyboard Shortcuts[/bold]

[cyan]Navigation:[/cyan]
  j/↓     Move down
  k/↑     Move up
  g       Go to top
  G       Go to bottom

[cyan]Selection:[/cyan]
  Space   Toggle selection
  Ctrl+A  Select all
  Escape  Clear selection

[cyan]Actions:[/cyan]
  d/Enter Show process details
  k       Kill process (SIGTERM)
  K       Force kill (SIGKILL)
  r       Toggle auto-refresh
  R       Manual refresh

[cyan]Views:[/cyan]
  n       Network connections
  t       Process tree
  D       Docker containers
  l       Process logs
  s       Systemd services
  H       Port heatmap
  g       Connection graph
  h       Kill history

[cyan]Filters & Alerts:[/cyan]
  /       Focus search
  c       Clear all filters
  a       Toggle alerts

[cyan]Other:[/cyan]
  ?       Show this help
  q       Quit
        """
        self.notify(help_text, title="Help", timeout=10)
