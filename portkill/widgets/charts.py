"""Charts and sparkline widgets."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from rich.text import Text

from portkill.utils.constants import SPARKLINE_CHARS


class Sparkline(Static):
    """A sparkline chart widget."""

    def __init__(
        self,
        data: list[float] | None = None,
        max_value: float | None = None,
        color: str = "#10b981",
        label: str = "",
        width: int = 30,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._data = data or []
        self._max_value = max_value
        self._color = color
        self._label = label
        self._width = width

    def update_data(self, data: list[float], max_value: float | None = None):
        """Update sparkline data."""
        self._data = data
        if max_value is not None:
            self._max_value = max_value
        self.refresh()

    def render(self) -> Text:
        """Render the sparkline."""
        if not self._data:
            bars = "─" * self._width
        else:
            # Normalize data
            max_val = self._max_value or max(self._data) or 1
            normalized = [min(1.0, v / max_val) for v in self._data]

            # Take last N values
            display_data = normalized[-self._width:]

            # Convert to sparkline characters
            chars = SPARKLINE_CHARS
            bars = ""
            for val in display_data:
                idx = int(val * (len(chars) - 1))
                bars += chars[idx]

            # Pad if needed
            if len(bars) < self._width:
                bars = "─" * (self._width - len(bars)) + bars

        text = Text()
        if self._label:
            text.append(f"{self._label} ", style="bold #71717a")
        text.append(bars, style=self._color)

        # Add current value
        if self._data:
            current = self._data[-1] if self._data else 0
            text.append(f" {current:.1f}%", style=f"bold {self._color}")
        else:
            text.append(f" 0.0%", style="#71717a")

        return text


class SystemCharts(Static):
    """Widget displaying system CPU and memory charts."""

    DEFAULT_CSS = """
    SystemCharts {
        height: 1;
        padding: 0 1;
        background: #1f1f23;
    }

    SystemCharts Horizontal {
        height: 1;
        align: center middle;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cpu_history: list[float] = []
        self._memory_history: list[float] = []

    def compose(self) -> ComposeResult:
        """Compose the charts."""
        yield Horizontal(
            Sparkline(label="CPU", color="#10b981", width=25, id="cpu-chart"),
            Static("  │  ", classes="separator"),
            Sparkline(label="MEM", color="#c084fc", width=25, id="mem-chart"),
        )

    def update_system_stats(self, cpu: float, memory: float):
        """Update system-wide stats."""
        self._cpu_history.append(cpu)
        self._memory_history.append(memory)

        # Keep last 60 values
        self._cpu_history = self._cpu_history[-60:]
        self._memory_history = self._memory_history[-60:]

        cpu_chart = self.query_one("#cpu-chart", Sparkline)
        mem_chart = self.query_one("#mem-chart", Sparkline)

        cpu_chart.update_data(self._cpu_history, max_value=100)
        mem_chart.update_data(self._memory_history, max_value=100)

    def update_process_stats(self, cpu_history: list[float], mem_history: list[float]):
        """Update selected process stats (no-op in compact mode)."""
        pass

    def clear_process_stats(self):
        """Clear process-specific stats (no-op in compact mode)."""
        pass
