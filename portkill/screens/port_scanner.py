"""Port Scanner screen for HTTP services."""

import socket
import ssl
import time
import threading
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static, DataTable, Input
from textual.containers import Horizontal, Container
from rich.text import Text

from portkill.widgets.custom_header import AsciiHeader


@dataclass
class ScanResult:
    """Result of a port scan."""
    port: int
    status: str  # open, closed, filtered
    service: str
    protocol: str  # HTTP, HTTPS, TCP
    response_time: float
    banner: str
    http_status: Optional[int] = None
    http_title: Optional[str] = None


class PortScannerScreen(Screen):
    """Screen for scanning ports and checking HTTP services."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("s", "start_scan", "Scan"),
        Binding("c", "scan_common", "Common Ports"),
        Binding("w", "scan_web", "Web Ports"),
        Binding("a", "scan_all", "All (1-1024)"),
        Binding("/", "focus_search", "Search"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    DEFAULT_CSS = """
    PortScannerScreen {
        background: #282828;
    }

    #input-bar {
        height: 3;
        width: 100%;
        padding: 1 2;
        background: #3c3836;
    }

    #input-bar Horizontal {
        height: 1;
        align: left middle;
    }

    #input-bar .label {
        width: auto;
        color: #a89984;
        padding: 0 1 0 0;
    }

    #input-bar .label-highlight {
        width: auto;
        color: #fe8019;
        text-style: bold;
        padding: 0 1 0 0;
    }

    #input-bar .separator {
        width: auto;
        color: #504945;
        padding: 0 1;
    }

    #input-bar .shortcut {
        width: auto;
        color: #8ec07c;
        text-style: bold;
        padding: 0;
    }

    #input-bar .shortcut-desc {
        width: auto;
        color: #a89984;
        padding: 0 1 0 0;
    }

    #input-bar Input {
        height: 1;
        background: #504945;
        border: hidden;
        padding: 0 1;
    }

    #input-bar Input:focus {
        background: #665c54;
        border: hidden;
    }

    #input-bar #target-input {
        width: 16;
    }

    #input-bar #search-input {
        width: 16;
    }

    #scan-table {
        height: 1fr;
        background: #282828;
    }

    #scan-table > .datatable--header {
        background: #3c3836;
        color: #8ec07c;
        text-style: bold;
    }

    #scan-table > .datatable--cursor {
        background: #504945;
    }

    #scan-table:focus > .datatable--cursor {
        background: #fe8019;
        color: #282828;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    # Common ports to scan
    COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 3306, 3389, 5432, 6379, 8080, 8443, 27017]
    WEB_PORTS = [80, 443, 3000, 3001, 4200, 5000, 5173, 8000, 8080, 8443, 8888, 9000, 9090]

    # Known services
    SERVICES = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        143: "IMAP",
        443: "HTTPS",
        445: "SMB",
        993: "IMAPS",
        995: "POP3S",
        3000: "Node.js",
        3001: "Dev Server",
        3306: "MySQL",
        3389: "RDP",
        4200: "Angular",
        5000: "Flask",
        5173: "Vite",
        5432: "PostgreSQL",
        6379: "Redis",
        8000: "HTTP Alt",
        8080: "HTTP Proxy",
        8443: "HTTPS Alt",
        8888: "HTTP Alt",
        9000: "PHP-FPM",
        9090: "Prometheus",
        27017: "MongoDB",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._target = "localhost"
        self._scanning = False
        self._results: list[ScanResult] = []
        self._stats = {"open": 0, "closed": 0, "http": 0, "https": 0}
        self._search_filter = ""

    def compose(self) -> ComposeResult:
        yield AsciiHeader()

        with Container(id="input-bar"):
            with Horizontal():
                yield Static("Target:", classes="label-highlight")
                yield Input(value="localhost", placeholder="host or IP", id="target-input")
                yield Static("│", classes="separator")
                yield Static("/", classes="shortcut")
                yield Input(placeholder="filter results...", id="search-input")
                yield Static("│", classes="separator")
                yield Static("c", classes="shortcut")
                yield Static(":common", classes="shortcut-desc")
                yield Static("w", classes="shortcut")
                yield Static(":web", classes="shortcut-desc")
                yield Static("a", classes="shortcut")
                yield Static(":all", classes="shortcut-desc")

        yield DataTable(id="scan-table")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table."""
        table = self.query_one("#scan-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        table.add_column("Port", width=8)
        table.add_column("Status", width=10)
        table.add_column("Service", width=14)
        table.add_column("Protocol", width=10)
        table.add_column("Response", width=10)
        table.add_column("HTTP Status", width=12)
        table.add_column("Title / Banner", width=35)

        self._update_stats()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        if event.input.id == "target-input":
            self._target = event.value or "localhost"
        elif event.input.id == "search-input":
            self._search_filter = event.value.lower()
            self._filter_results()

    def _filter_results(self) -> None:
        """Filter and redisplay results based on search."""
        table = self.query_one("#scan-table", DataTable)
        table.clear()

        for result in self._results:
            # Check if result matches filter
            if self._search_filter:
                search_text = f"{result.port} {result.service} {result.protocol} {result.status} {result.http_title or ''} {result.banner}".lower()
                if self._search_filter not in search_text:
                    continue

            self._add_result_row(result)

    def action_focus_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def action_start_scan(self) -> None:
        """Start a custom scan."""
        self.notify("Use 'c' for common, 'w' for web, 'a' for all ports")

    def action_scan_common(self) -> None:
        """Scan common ports."""
        if self._scanning:
            self.notify("Scan already in progress", severity="warning")
            return
        self._run_scan(self.COMMON_PORTS)

    def action_scan_web(self) -> None:
        """Scan web-related ports."""
        if self._scanning:
            self.notify("Scan already in progress", severity="warning")
            return
        self._run_scan(self.WEB_PORTS)

    def action_scan_all(self) -> None:
        """Scan all ports 1-1024."""
        if self._scanning:
            self.notify("Scan already in progress", severity="warning")
            return
        self._run_scan(list(range(1, 1025)))

    def _run_scan(self, ports: list[int]) -> None:
        """Run the port scan."""
        table = self.query_one("#scan-table", DataTable)
        table.clear()
        self._results.clear()
        self._stats = {"open": 0, "closed": 0, "http": 0, "https": 0, "total": len(ports)}
        self._scanning = True
        self._update_stats(scanning=True)
        self.notify(f"Scanning {len(ports)} ports on {self._target}...")

        # Start scan in background thread
        scan_thread = threading.Thread(target=self._scan_ports, args=(ports,), daemon=True)
        scan_thread.start()

    def _scan_ports(self, ports: list[int]) -> None:
        """Scan ports in background."""
        try:
            with ThreadPoolExecutor(max_workers=50) as executor:
                futures = {executor.submit(self._scan_port, port): port for port in ports}

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            self._results.append(result)
                            self.app.call_from_thread(self._add_result_row, result)
                    except Exception:
                        pass

        finally:
            self._scanning = False
            self.app.call_from_thread(self._update_stats)
            self.app.call_from_thread(self.notify, "Scan complete")

    def _scan_port(self, port: int) -> Optional[ScanResult]:
        """Scan a single port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)

        start_time = time.time()
        try:
            result = sock.connect_ex((self._target, port))
            response_time = (time.time() - start_time) * 1000  # ms

            if result == 0:
                self._stats["open"] += 1

                # Port is open - try to identify service
                service = self.SERVICES.get(port, "Unknown")
                protocol = "TCP"
                banner = ""
                http_status = None
                http_title = None

                # Try HTTP/HTTPS detection
                if port in [80, 8080, 8000, 3000, 5000, 8888, 4200, 5173, 3001, 9000, 9090]:
                    http_result = self._check_http(port, use_ssl=False)
                    if http_result:
                        protocol = "HTTP"
                        http_status, http_title = http_result
                        self._stats["http"] += 1

                elif port in [443, 8443, 9443]:
                    http_result = self._check_http(port, use_ssl=True)
                    if http_result:
                        protocol = "HTTPS"
                        http_status, http_title = http_result
                        self._stats["https"] += 1

                else:
                    # Try to get banner
                    banner = self._get_banner(sock, port)

                return ScanResult(
                    port=port,
                    status="open",
                    service=service,
                    protocol=protocol,
                    response_time=response_time,
                    banner=banner[:35] if banner else "",
                    http_status=http_status,
                    http_title=http_title[:35] if http_title else None
                )
            else:
                self._stats["closed"] += 1
                return None

        except socket.timeout:
            return ScanResult(
                port=port,
                status="filtered",
                service=self.SERVICES.get(port, "Unknown"),
                protocol="TCP",
                response_time=2000,
                banner=""
            )
        except Exception:
            return None
        finally:
            sock.close()

    def _check_http(self, port: int, use_ssl: bool = False) -> Optional[tuple[int, str]]:
        """Check if port responds to HTTP and get status/title."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((self._target, port))

            if use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock, server_hostname=self._target)

            # Send HTTP request
            request = f"GET / HTTP/1.1\r\nHost: {self._target}\r\nConnection: close\r\n\r\n"
            sock.send(request.encode())

            response = sock.recv(4096).decode('utf-8', errors='ignore')
            sock.close()

            # Parse response
            if response.startswith("HTTP/"):
                lines = response.split("\r\n")
                status_line = lines[0]
                try:
                    status_code = int(status_line.split()[1])
                except (IndexError, ValueError):
                    status_code = 0

                # Try to find title
                title = ""
                if "<title>" in response.lower():
                    start = response.lower().find("<title>") + 7
                    end = response.lower().find("</title>")
                    if end > start:
                        title = response[start:end].strip()

                return (status_code, title)

        except Exception:
            pass

        return None

    def _get_banner(self, sock: socket.socket, port: int) -> str:
        """Try to get service banner."""
        try:
            # For some services, send a probe
            if port in [21, 22, 25, 110, 143]:
                sock.settimeout(2)
                banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                return banner[:50]
        except Exception:
            pass
        return ""

    def _add_result_row(self, result: ScanResult) -> None:
        """Add a scan result row to the table."""
        table = self.query_one("#scan-table", DataTable)

        # Status styling
        if result.status == "open":
            status_text = Text("OPEN", style="bold #b8bb26")
        elif result.status == "filtered":
            status_text = Text("FILTERED", style="#fabd2f")
        else:
            status_text = Text("CLOSED", style="#fb4934")

        # Protocol styling
        if result.protocol == "HTTPS":
            proto_text = Text("HTTPS", style="bold #b8bb26")
        elif result.protocol == "HTTP":
            proto_text = Text("HTTP", style="#83a598")
        else:
            proto_text = Text(result.protocol, style="#a89984")

        # HTTP status styling
        if result.http_status:
            if 200 <= result.http_status < 300:
                http_text = Text(str(result.http_status), style="bold #b8bb26")
            elif 300 <= result.http_status < 400:
                http_text = Text(str(result.http_status), style="#83a598")
            elif 400 <= result.http_status < 500:
                http_text = Text(str(result.http_status), style="#fabd2f")
            else:
                http_text = Text(str(result.http_status), style="#fb4934")
        else:
            http_text = Text("-", style="#665c54")

        # Title/Banner
        display_text = result.http_title or result.banner or "-"

        table.add_row(
            Text(str(result.port), style="bold #fe8019"),
            status_text,
            Text(result.service, style="#ebdbb2"),
            proto_text,
            Text(f"{result.response_time:.0f}ms", style="#a89984"),
            http_text,
            Text(display_text[:34], style="#8ec07c" if display_text != "-" else "#665c54"),
        )

        self._update_stats()

    def _update_stats(self, scanning: bool = False) -> None:
        """Update the stats bar."""
        stats_bar = self.query_one("#stats-bar", Static)

        text = Text()
        text.append(f" Target: ", style="#a89984")
        text.append(f"{self._target}", style="bold #ebdbb2")
        text.append(f"  |  Open: ", style="#a89984")
        text.append(f"{self._stats['open']}", style="bold #b8bb26")
        text.append(f"  |  HTTP: ", style="#a89984")
        text.append(f"{self._stats['http']}", style="#83a598")
        text.append(f"  HTTPS: ", style="#a89984")
        text.append(f"{self._stats['https']}", style="#b8bb26")

        if scanning or self._scanning:
            text.append(f"  |  ", style="#a89984")
            text.append("SCANNING...", style="bold #fabd2f")

        stats_bar.update(text)

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one("#scan-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one("#scan-table", DataTable)
        table.action_cursor_up()
