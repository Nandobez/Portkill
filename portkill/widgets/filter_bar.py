"""Filter bar widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Select, Static, Switch
from textual.message import Message

from portkill.utils.constants import ServiceType, ProcessStatus


class FilterBar(Static):
    """Compact filter bar for processes - single line."""

    DEFAULT_CSS = """
    FilterBar {
        height: 3;
        width: 100%;
        padding: 1 2;
        background: #3c3836;
    }

    FilterBar Horizontal {
        height: 1;
        align: left middle;
    }

    FilterBar .label {
        width: auto;
        color: #a89984;
        padding: 0 1 0 0;
    }

    FilterBar .label-highlight {
        width: auto;
        color: #d3869b;
        text-style: bold;
        padding: 0 1 0 0;
    }

    FilterBar .separator {
        width: auto;
        color: #504945;
        padding: 0 1;
    }

    FilterBar .value {
        width: auto;
        color: #ebdbb2;
        padding: 0 1 0 0;
    }

    FilterBar .value-active {
        width: auto;
        color: #b8bb26;
        text-style: bold;
        padding: 0 1 0 0;
    }

    FilterBar .value-inactive {
        width: auto;
        color: #665c54;
        padding: 0 1 0 0;
    }

    FilterBar Switch {
        height: 1;
        width: auto;
        min-width: 4;
        background: #504945;
        border: none;
        padding: 0;
    }

    FilterBar Switch:focus {
        background: #504945;
    }

    FilterBar Switch.-on {
        background: #b8bb26;
    }

    FilterBar Select {
        height: 1;
        width: 12;
        background: #504945;
        border: none;
        padding: 0;
    }

    FilterBar Select:focus {
        background: #665c54;
        border: none;
    }

    FilterBar SelectCurrent {
        height: 1;
        background: #504945;
        border: none;
        padding: 0 1;
    }

    FilterBar SelectOverlay {
        background: #3c3836;
        border: solid #fe8019;
    }

    FilterBar Input {
        height: 1;
        background: #504945;
        border: hidden;
        padding: 0 1;
    }

    FilterBar Input:focus {
        background: #665c54;
        border: hidden;
    }

    FilterBar #port-input {
        width: 8;
    }

    FilterBar #search-input {
        width: 1fr;
        min-width: 15;
    }
    """

    class FiltersChanged(Message):
        """Message sent when filters change."""

        def __init__(
            self,
            service_type: ServiceType | None,
            status: ProcessStatus | None,
            protocol: str | None,
            port: int | None,
            port_range: tuple[int, int] | None,
            search: str,
            show_all_dev: bool,
        ):
            self.service_type = service_type
            self.status = status
            self.protocol = protocol
            self.port = port
            self.port_range = port_range
            self.search = search
            self.show_all_dev = show_all_dev
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._show_all_dev = True
        self._service_type: ServiceType | None = None
        self._status: ProcessStatus | None = None
        self._protocol: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the filter bar."""
        # Service type options
        service_options = [("All", None)] + [
            (st.value.capitalize(), st) for st in ServiceType
        ]

        with Horizontal():
            # All Dev switch
            yield Static("All Dev", classes="label")
            yield Switch(value=True, id="all-dev-switch")
            yield Static("│", classes="separator")

            # Service type select
            yield Static("Service:", classes="label")
            yield Select(
                [(label, value) for label, value in service_options],
                value=None,
                allow_blank=False,
                id="service-select",
            )
            yield Static("│", classes="separator")

            # Port filter
            yield Static("Port:", classes="label")
            yield Input(placeholder="8080", id="port-input")
            yield Static("│", classes="separator")

            # Search
            yield Static("🔍", classes="label")
            yield Input(placeholder="search...", id="search-input")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        self._emit_filters()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch toggle."""
        if event.switch.id == "all-dev-switch":
            self._show_all_dev = event.value
            self._emit_filters()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes."""
        if event.select.id == "service-select":
            self._service_type = event.value
            self._emit_filters()

    def _emit_filters(self) -> None:
        """Emit current filter state."""
        # Get port filter
        port_input = self.query_one("#port-input", Input)
        port_text = port_input.value.strip()
        port = None
        port_range = None

        if port_text:
            if "-" in port_text:
                try:
                    parts = port_text.split("-")
                    port_range = (int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    pass
            else:
                try:
                    port = int(port_text)
                except ValueError:
                    pass

        # Get search
        search_input = self.query_one("#search-input", Input)
        search = search_input.value.strip()

        self.post_message(
            self.FiltersChanged(
                service_type=self._service_type,
                status=self._status,
                protocol=self._protocol,
                port=port,
                port_range=port_range,
                search=search,
                show_all_dev=self._show_all_dev,
            )
        )

    def clear_filters(self) -> None:
        """Clear all filters."""
        self._service_type = None
        self._status = None
        self._protocol = None
        self._show_all_dev = True

        # Reset UI controls
        self.query_one("#all-dev-switch", Switch).value = True
        self.query_one("#service-select", Select).value = None
        self.query_one("#port-input", Input).value = ""
        self.query_one("#search-input", Input).value = ""
        self._emit_filters()

    def focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()
