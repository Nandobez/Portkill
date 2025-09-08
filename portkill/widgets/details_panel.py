"""Details panel widget for showing process information."""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Grid
from textual.widgets import Static
from textual.reactive import reactive
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.console import Group

from portkill.models.process import PortProcess


class DetailsPanel(Static):
    """Panel showing detailed information about a process."""

    DEFAULT_CSS = """
    DetailsPanel {
        height: auto;
        max-height: 10;
        background: #32302f;
        border: solid #fe8019;
        border-title-color: #fabd2f;
        padding: 0 1;
        margin: 0;
    }
    """

    process: reactive[PortProcess | None] = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._process: PortProcess | None = None

    def update_process(self, process: PortProcess | None) -> None:
        """Update the displayed process."""
        self._process = process
        self.refresh()

    def render(self) -> Panel:
        """Render the details panel."""
        if not self._process:
            return Panel(
                Text("  Select a process and press 'd' to view details", style="dim italic #665c54"),
                title="[bold #fabd2f]  Process Details[/]",
                border_style="#504945",
                padding=(0, 1),
            )

        proc = self._process

        # Create two columns layout
        left_col = Table(show_header=False, box=None, padding=(0, 1, 0, 0), expand=True)
        left_col.add_column("Label", style="bold #a89984", width=10)
        left_col.add_column("Value", style="#ebdbb2")

        right_col = Table(show_header=False, box=None, padding=(0, 1, 0, 0), expand=True)
        right_col.add_column("Label", style="bold #a89984", width=10)
        right_col.add_column("Value", style="#ebdbb2")

        # Left column - Basic info
        left_col.add_row("PID", Text(str(proc.pid), style="bold #fabd2f"))
        left_col.add_row("Name", Text(proc.name, style="bold #ebdbb2"))
        left_col.add_row("Status", Text(f"{proc.status_icon} {proc.status_label}", style=proc.status_color))
        left_col.add_row("Service", Text(f"● {proc.service_type.value}", style=proc.color))
        left_col.add_row("User", Text(proc.username, style="#a89984"))

        # Right column - Resources & Network
        right_col.add_row("CPU", self._format_cpu(proc.cpu_percent))
        right_col.add_row("Memory", Text(proc.memory_display, style="#d3869b"))
        right_col.add_row("Uptime", Text(proc.uptime, style="#a89984"))
        right_col.add_row("Net I/O", Text(proc.network_io_display, style="#8ec07c"))

        if proc.port > 0:
            right_col.add_row("Port", Text(f"{proc.port} ({proc.protocol})", style="#b8bb26"))
            if proc.connection_status:
                right_col.add_row("State", Text(proc.connection_status, style="#83a598"))
        else:
            right_col.add_row("Port", Text("—", style="#665c54"))

        # Create columns layout
        columns = Columns([left_col, right_col], equal=True, expand=True)

        # Command line at bottom
        cmd_text = proc.cmdline if len(proc.cmdline) <= 120 else proc.cmdline[:117] + "..."
        cmd_line = Text()
        cmd_line.append("Command: ", style="bold #a89984")
        cmd_line.append(cmd_text, style="#a89984")

        content = Group(columns, Text(""), cmd_line)

        return Panel(
            content,
            title=f"[bold #fabd2f]  {proc.name}[/] [dim #665c54](PID: {proc.pid})[/]",
            border_style="#fe8019",
            padding=(0, 1),
        )

    def _format_cpu(self, cpu: float) -> Text:
        """Format CPU usage with color based on usage."""
        if cpu > 80:
            color = "#fb4934"
        elif cpu > 50:
            color = "#fabd2f"
        elif cpu > 20:
            color = "#b8bb26"
        else:
            color = "#a89984"
        return Text(f"{cpu:.1f}%", style=color)
