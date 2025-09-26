"""Confirmation dialog screen."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal, Center
from textual.widgets import Static, Button, Label
from textual.binding import Binding
from rich.text import Text


class ConfirmDialog(ModalScreen[bool]):
    """Modal confirmation dialog."""

    BINDINGS = [
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
    ]

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
        background: rgba(40, 40, 40, 0.85);
    }

    #dialog-container {
        width: 60;
        height: auto;
        background: #3c3836;
        border: solid #fe8019;
        padding: 1 2;
    }

    #dialog-title {
        text-align: center;
        text-style: bold;
        color: #fe8019;
        padding-bottom: 1;
        width: 100%;
    }

    #dialog-body {
        text-align: center;
        color: #ebdbb2;
        padding-bottom: 1;
        width: 100%;
    }

    #dialog-details {
        text-align: center;
        color: #a89984;
        padding-bottom: 1;
        width: 100%;
    }

    #dialog-buttons {
        align: center middle;
        height: auto;
        width: 100%;
        padding-top: 1;
    }

    #dialog-buttons Button {
        margin: 0 2;
        min-width: 12;
    }

    #btn-confirm {
        background: #fb4934;
        color: #282828;
    }

    #btn-confirm:hover {
        background: #cc241d;
    }

    #btn-cancel {
        background: #504945;
        color: #ebdbb2;
    }

    #btn-cancel:hover {
        background: #665c54;
    }

    .warning-icon {
        text-align: center;
        color: #fabd2f;
        padding-bottom: 1;
    }
    """

    def __init__(
        self,
        title: str = "Confirm",
        message: str = "Are you sure?",
        details: str = "",
        confirm_label: str = "Yes",
        cancel_label: str = "No",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.title_text = title
        self.message = message
        self.details = details
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Static("⚠", classes="warning-icon")
            yield Static(self.title_text, id="dialog-title")
            yield Static(self.message, id="dialog-body")
            if self.details:
                yield Static(self.details, id="dialog-details")
            with Center():
                with Horizontal(id="dialog-buttons"):
                    yield Button(self.confirm_label, id="btn-confirm", variant="error")
                    yield Button(self.cancel_label, id="btn-cancel")

    def action_confirm(self) -> None:
        """Confirm action."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel action."""
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)


class KillConfirmDialog(ConfirmDialog):
    """Specialized confirmation dialog for kill operations."""

    def __init__(
        self,
        process_name: str,
        pid: int,
        port: int | None = None,
        count: int = 1,
        force: bool = False,
        **kwargs
    ):
        signal_type = "SIGKILL (force)" if force else "SIGTERM"

        if count == 1:
            title = "Kill Process?"
            message = f"Kill [bold #fabd2f]{process_name}[/] (PID: {pid})?"
            if port and port > 0:
                details = f"Port: {port} | Signal: {signal_type}"
            else:
                details = f"Signal: {signal_type}"
        else:
            title = f"Kill {count} Processes?"
            message = f"Kill [bold #fabd2f]{count}[/] selected processes?"
            details = f"Signal: {signal_type}"

        super().__init__(
            title=title,
            message=message,
            details=details,
            confirm_label="Kill" if not force else "Force Kill",
            cancel_label="Cancel",
            **kwargs
        )
