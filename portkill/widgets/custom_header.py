"""Custom header widget with ASCII art."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Center
from textual.widgets import Static
from rich.text import Text
from rich.align import Align
from rich.console import Group


PORTKILL_ASCII = r"""
██████╗  ██████╗ ██████╗ ████████╗██╗  ██╗██╗██╗     ██╗
██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝██║ ██╔╝██║██║     ██║
██████╔╝██║   ██║██████╔╝   ██║   █████╔╝ ██║██║     ██║
██╔═══╝ ██║   ██║██╔══██╗   ██║   ██╔═██╗ ██║██║     ██║
██║     ╚██████╔╝██║  ██║   ██║   ██║  ██╗██║███████╗███████╗
╚═╝     ╚═════╝  ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝
"""


class AsciiHeader(Static):
    """Large ASCII art header."""

    DEFAULT_CSS = """
    AsciiHeader {
        height: auto;
        width: 100%;
        background: #282828;
        padding: 1 0;
        text-align: center;
    }
    """

    def render(self) -> Text:
        """Render the ASCII art header."""
        lines = PORTKILL_ASCII.strip().split('\n')

        # Pad all lines to the same length for proper centering
        max_len = max(len(line) for line in lines)
        lines = [line.ljust(max_len) for line in lines]

        text = Text(justify="center")

        for i, line in enumerate(lines):
            if i > 0:
                text.append("\n")

            # Create gradient using Gruvbox colors
            line_len = len(line.rstrip())  # Use original length for gradient
            for j, char in enumerate(line):
                progress = j / max(line_len - 1, 1) if line_len > 1 else 0

                if char in '█▀▄╗╔╝╚║═':
                    # Gradient: aqua (#8ec07c) -> yellow (#fabd2f) -> orange (#fe8019)
                    if progress < 0.4:
                        style = "bold #8ec07c"
                    elif progress < 0.7:
                        style = "bold #fabd2f"
                    else:
                        style = "bold #fe8019"
                    text.append(char, style=style)
                else:
                    text.append(char)

        return text


class CompactHeader(Static):
    """Compact single-line header for small terminals."""

    DEFAULT_CSS = """
    CompactHeader {
        height: 1;
        background: #3c3836;
        padding: 0 2;
        border-bottom: solid #504945;
    }
    """

    def render(self) -> Text:
        """Render the header."""
        text = Text()
        text.append("⚡ ", style="bold #fabd2f")
        text.append("PORT", style="bold #8ec07c")
        text.append("KILL", style="bold #fb4934")
        text.append(" │ ", style="dim #504945")
        text.append("Process & Port Manager", style="#a89984")
        text.append("  │  ", style="dim #504945")
        text.append("d", style="bold #fe8019")
        text.append(":details ", style="dim")
        text.append("k", style="bold #fe8019")
        text.append(":kill ", style="dim")
        text.append("?", style="bold #fe8019")
        text.append(":help", style="dim")
        return text
