"""Main PortKill application."""

from pathlib import Path
from textual.app import App

from portkill.services.process_manager import ProcessManager
from portkill.screens.main import MainScreen


class PortKillApp(App):
    """PortKill TUI Application."""

    TITLE = "PortKill"
    SUB_TITLE = "Process & Port Manager"

    CSS_PATH = Path(__file__).parent / "styles" / "theme.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.process_manager = ProcessManager()

    def on_mount(self) -> None:
        """Handle mount event."""
        self.push_screen(MainScreen(self.process_manager))


def run():
    """Run the PortKill application."""
    app = PortKillApp()
    app.run()


if __name__ == "__main__":
    run()
