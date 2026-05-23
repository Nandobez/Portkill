"""Process table widget."""

import shutil
from textual.binding import Binding
from textual.widgets import DataTable
from textual.message import Message
from rich.text import Text

from portkill.models.process import PortProcess


class ProcessTable(DataTable):
    """Interactive table displaying processes with ports."""

    DEFAULT_CSS = """
    ProcessTable {
        width: 100%;
        background: #282828;
        scrollbar-background: #3c3836;
        scrollbar-color: #504945;
        scrollbar-color-hover: #fe8019;
        scrollbar-color-active: #fabd2f;
    }

    ProcessTable > .datatable--header {
        background: #3c3836;
        color: #8ec07c;
        text-style: bold;
    }

    ProcessTable > .datatable--cursor {
        background: #504945;
        color: #ebdbb2;
    }

    ProcessTable:focus > .datatable--cursor {
        background: #fe8019;
        color: #282828;
    }

    ProcessTable > .datatable--hover {
        background: #3c3836;
    }

    ProcessTable > .datatable--even-row {
        background: #282828;
    }

    ProcessTable > .datatable--odd-row {
        background: #32302f;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("space", "toggle_select", "Select", show=True),
        Binding("ctrl+a", "select_all", "Select All", show=False),
    ]

    class ProcessToggled(Message):
        """Message sent when a process selection is toggled."""

        def __init__(self, pid: int) -> None:
            self.pid = pid
            super().__init__()

    class SelectAllRequested(Message):
        """Message sent when select all is requested."""
        pass

    # Fixed column widths
    FIXED_WIDTHS = {
        "select": 3,
        "pid": 8,
        "port": 6,
        "proto": 6,
        "status": 7,
        "service": 11,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._processes: list[PortProcess] = []
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._columns_added = False

    def on_mount(self) -> None:
        """Set up the table columns."""
        # Set up columns immediately with default width
        self._setup_columns()
        # Schedule width update after layout is complete
        self.call_after_refresh(self._update_command_column_width)
        # Also schedule a delayed update to catch late layout changes
        self.set_timer(0.1, self._update_command_column_width)

    def on_resize(self, event) -> None:
        """Handle resize to update Command column width."""
        if self._columns_added:
            self._update_command_column_width()

    def _setup_columns(self) -> None:
        """Set up table columns with calculated widths."""
        if self._columns_added:
            return

        self.add_column("", width=self.FIXED_WIDTHS["select"], key="select")
        self.add_column("PID", width=self.FIXED_WIDTHS["pid"], key="pid")
        self.add_column("Port", width=self.FIXED_WIDTHS["port"], key="port")
        self.add_column("Proto", width=self.FIXED_WIDTHS["proto"], key="proto")
        self.add_column("Status", width=self.FIXED_WIDTHS["status"], key="status")
        self.add_column("Service", width=self.FIXED_WIDTHS["service"], key="service")
        # Command column - calculate width based on screen size
        cmd_width = self._calculate_command_width()
        self.add_column("Command", width=cmd_width, key="command")
        self._columns_added = True

    def _calculate_command_width(self) -> int:
        """Calculate width for Command column to fill remaining space."""
        # Use a large fixed width - table will handle scrolling if needed
        return 300

    def _update_command_column_width(self) -> None:
        """Update Command column width on resize."""
        if not self._columns_added:
            return
        try:
            cmd_width = self._calculate_command_width()
            for col_key in self.columns:
                if col_key.value == "command":
                    self.columns[col_key].width = cmd_width
                    break
            self.refresh()
        except Exception:
            pass  # Ignore errors during resize

    def update_processes(self, processes: list[PortProcess]) -> None:
        """Update the table with new process data."""
        # Store current cursor position
        current_row = self.cursor_row

        # Clear existing data
        self.clear()
        self._processes = processes.copy()

        # Add rows
        for proc in processes:
            port_str = str(proc.port) if proc.port > 0 else "—"
            proto_str = proc.protocol if proc.port > 0 else "—"
            self.add_row(
                self._format_checkbox(proc.selected),
                self._format_pid(proc.pid),
                self._format_port(port_str),
                Text(proto_str, style="#71717a" if proto_str == "—" else "#a1a1aa"),
                self._format_status(proc),
                self._format_service(proc),
                self._format_command(proc.short_command),
            )

        # Restore cursor position if possible
        if current_row is not None and current_row < len(processes) and len(processes) > 0:
            self.move_cursor(row=current_row)

    def _format_checkbox(self, selected: bool) -> Text:
        """Format selection checkbox."""
        if selected:
            return Text("✓", style="bold #b8bb26")
        return Text("○", style="#504945")

    def _format_pid(self, pid: int) -> Text:
        """Format PID."""
        return Text(str(pid), style="#fabd2f")

    def _format_port(self, port: str) -> Text:
        """Format port."""
        if port == "—":
            return Text(port, style="#665c54")
        return Text(port, style="#b8bb26")

    def _format_status(self, proc: PortProcess) -> Text:
        """Format process status with icon and color."""
        icon = proc.status_info[2]
        color = proc.status_info[1]
        return Text(f"{icon}", style=color)

    def _format_service(self, proc: PortProcess) -> Text:
        """Format service type with color."""
        service_name = proc.service_type.value.capitalize()
        return Text(f"● {service_name}", style=proc.color)

    def _format_command(self, cmd: str) -> Text:
        """Format command with subtle styling."""
        return Text(cmd, style="#a89984")

    def get_current_process(self) -> PortProcess | None:
        """Get the currently highlighted process."""
        if self.cursor_row is not None and self.cursor_row < len(self._processes):
            return self._processes[self.cursor_row]
        return None

    def get_selected_processes(self) -> list[PortProcess]:
        """Get all selected processes."""
        return [p for p in self._processes if p.selected]

    def action_toggle_select(self) -> None:
        """Toggle selection of current row."""
        proc = self.get_current_process()
        if proc:
            self.post_message(self.ProcessToggled(proc.pid))

    def action_select_all(self) -> None:
        """Request select all."""
        self.post_message(self.SelectAllRequested())

    def action_scroll_top(self) -> None:
        """Scroll to top."""
        if len(self._processes) > 0:
            self.move_cursor(row=0)

    def action_scroll_bottom(self) -> None:
        """Scroll to bottom."""
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)
