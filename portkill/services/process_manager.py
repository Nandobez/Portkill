"""Process management service using psutil."""

import os
import signal
from datetime import datetime
from typing import Optional

import psutil

from portkill.models.process import PortProcess
from portkill.models.history import KillRecord, HistoryDB
from portkill.utils.constants import ProcessStatus, ServiceType, SERVICE_PATTERNS


# Patterns to identify development processes (even without ports)
DEV_PROCESS_PATTERNS = [
    # Java
    "java", "javac", "mvn", "gradle", "kotlin", "groovy",
    # JavaScript/Node
    "node", "npm", "npx", "yarn", "pnpm", "bun", "deno", "ts-node",
    # Python
    "python", "python3", "pip", "uvicorn", "gunicorn", "flask", "django", "fastapi",
    # C/C++
    "gcc", "g++", "clang", "clang++", "make", "cmake", "gdb", "lldb",
    # Rust
    "cargo", "rustc", "rust-analyzer",
    # Go
    "go", "air",
    # Elixir/Erlang
    "elixir", "mix", "iex", "erl", "beam", "beam.smp",
    # Ruby
    "ruby", "rails", "bundle", "rake",
    # PHP
    "php", "composer", "artisan",
    # Docker
    "docker", "docker-compose", "podman",
    # Databases
    "postgres", "postgresql", "mysql", "mysqld", "mongod", "redis-server", "rabbitmq",
    # Web servers
    "nginx", "apache", "httpd", "caddy",
    # Other dev tools
    "webpack", "vite", "esbuild", "rollup", "parcel",
]


class ProcessManager:
    """Manages system processes and ports."""

    # Map psutil status to our ProcessStatus
    STATUS_MAP = {
        psutil.STATUS_RUNNING: ProcessStatus.RUNNING,
        psutil.STATUS_SLEEPING: ProcessStatus.SLEEPING,
        psutil.STATUS_DISK_SLEEP: ProcessStatus.DISK_SLEEP,
        psutil.STATUS_STOPPED: ProcessStatus.STOPPED,
        psutil.STATUS_ZOMBIE: ProcessStatus.ZOMBIE,
        psutil.STATUS_DEAD: ProcessStatus.DEAD,
        psutil.STATUS_IDLE: ProcessStatus.IDLE,
    }

    def __init__(self, history_db: Optional[HistoryDB] = None):
        """Initialize the process manager."""
        self.history_db = history_db or HistoryDB()
        self._process_cache: dict[int, PortProcess] = {}

    def get_port_processes(
        self,
        port_filter: Optional[int] = None,
        port_range: Optional[tuple[int, int]] = None,
        service_filter: Optional[ServiceType] = None,
        status_filter: Optional[ProcessStatus] = None,
        protocol_filter: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> list[PortProcess]:
        """Get all processes with open ports, with optional filters."""
        processes: dict[tuple[int, int], PortProcess] = {}

        try:
            connections = psutil.net_connections(kind="inet")
        except psutil.AccessDenied:
            # Try with just TCP/UDP
            try:
                connections = psutil.net_connections(kind="tcp")
                connections.extend(psutil.net_connections(kind="udp"))
            except psutil.AccessDenied:
                return []

        for conn in connections:
            # Skip connections without local address or PID
            if not conn.laddr or not conn.pid:
                continue

            port = conn.laddr.port
            pid = conn.pid

            # Apply port filter
            if port_filter is not None and port != port_filter:
                continue

            # Apply port range filter
            if port_range is not None:
                if port < port_range[0] or port > port_range[1]:
                    continue

            # Apply protocol filter
            protocol = "TCP" if conn.type == 1 else "UDP"
            if protocol_filter and protocol != protocol_filter.upper():
                continue

            # Create unique key for process+port
            key = (pid, port)
            if key in processes:
                continue

            try:
                proc = psutil.Process(pid)
                proc_info = proc.as_dict(
                    attrs=[
                        "name",
                        "cmdline",
                        "username",
                        "status",
                        "cpu_percent",
                        "memory_info",
                        "create_time",
                    ]
                )

                # Get command line
                cmdline = proc_info.get("cmdline") or []
                cmdline_str = " ".join(cmdline) if cmdline else proc_info.get("name", "")

                # Get status
                status_str = proc_info.get("status", "")
                status = self.STATUS_MAP.get(status_str, ProcessStatus.UNKNOWN)

                # Get memory in MB
                memory_info = proc_info.get("memory_info")
                memory_mb = memory_info.rss / (1024 * 1024) if memory_info else 0

                # Get remote address
                remote_addr = ""
                if conn.raddr:
                    remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}"

                # Get I/O counters if available
                bytes_sent = 0
                bytes_recv = 0
                try:
                    io_counters = proc.io_counters()
                    if io_counters:
                        bytes_sent = io_counters.write_bytes
                        bytes_recv = io_counters.read_bytes
                except (psutil.AccessDenied, AttributeError):
                    pass

                # Count connections for this process
                conn_count = sum(1 for c in connections if c.pid == pid)

                # Create process object
                port_process = PortProcess(
                    pid=pid,
                    port=port,
                    protocol=protocol,
                    name=proc_info.get("name", "unknown"),
                    cmdline=cmdline_str,
                    username=proc_info.get("username", "unknown"),
                    status=status,
                    cpu_percent=proc_info.get("cpu_percent", 0) or 0,
                    memory_mb=memory_mb,
                    create_time=datetime.fromtimestamp(
                        proc_info.get("create_time", 0)
                    ),
                    local_address=f"{conn.laddr.ip}:{conn.laddr.port}",
                    remote_address=remote_addr,
                    connection_status=conn.status if hasattr(conn, "status") else "",
                    bytes_sent=bytes_sent,
                    bytes_recv=bytes_recv,
                    connections_count=conn_count,
                )

                # Update history from cache
                if pid in self._process_cache:
                    cached = self._process_cache[pid]
                    port_process.cpu_history = cached.cpu_history.copy()
                    port_process.memory_history = cached.memory_history.copy()
                    port_process.selected = cached.selected

                # Update metrics
                port_process.update_metrics(port_process.cpu_percent, memory_mb)

                # Apply service filter
                if service_filter and port_process.service_type != service_filter:
                    continue

                # Apply status filter
                if status_filter and port_process.status != status_filter:
                    continue

                # Apply search query
                if search_query:
                    query = search_query.lower()
                    searchable = (
                        f"{port_process.name} {port_process.cmdline} "
                        f"{port_process.username} {port_process.port}"
                    ).lower()
                    if query not in searchable:
                        continue

                processes[key] = port_process
                self._process_cache[pid] = port_process

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort by port number
        result = sorted(processes.values(), key=lambda p: (p.port, p.pid))
        return result

    def get_dev_processes(
        self,
        service_filter: Optional[ServiceType] = None,
        status_filter: Optional[ProcessStatus] = None,
        search_query: Optional[str] = None,
        include_ports: bool = True,
    ) -> list[PortProcess]:
        """Get all development processes (with or without ports)."""
        processes: dict[int, PortProcess] = {}

        # First, get processes with ports if requested
        port_pids: set[int] = set()
        if include_ports:
            port_processes = self.get_port_processes(
                service_filter=service_filter,
                status_filter=status_filter,
                search_query=search_query,
            )
            for p in port_processes:
                processes[p.pid] = p
                port_pids.add(p.pid)

        # Now scan all processes for development patterns
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username', 'status',
                                          'cpu_percent', 'memory_info', 'create_time']):
            try:
                pid = proc.info['pid']

                # Skip if already added from port processes
                if pid in port_pids:
                    continue

                name = proc.info.get('name', '') or ''
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline) if cmdline else name

                # Check if this is a development process
                is_dev_process = False
                name_lower = name.lower()
                cmdline_lower = cmdline_str.lower()

                for pattern in DEV_PROCESS_PATTERNS:
                    if pattern in name_lower or pattern in cmdline_lower:
                        is_dev_process = True
                        break

                if not is_dev_process:
                    continue

                # Get status
                status_str = proc.info.get('status', '')
                status = self.STATUS_MAP.get(status_str, ProcessStatus.UNKNOWN)

                # Get memory in MB
                memory_info = proc.info.get('memory_info')
                memory_mb = memory_info.rss / (1024 * 1024) if memory_info else 0

                # Get I/O counters if available
                bytes_sent = 0
                bytes_recv = 0
                try:
                    io_counters = proc.io_counters()
                    if io_counters:
                        bytes_sent = io_counters.write_bytes
                        bytes_recv = io_counters.read_bytes
                except (psutil.AccessDenied, AttributeError):
                    pass

                # Create process object (port=0 for non-port processes)
                dev_process = PortProcess(
                    pid=pid,
                    port=0,  # No port
                    protocol="-",
                    name=name,
                    cmdline=cmdline_str,
                    username=proc.info.get('username', 'unknown') or 'unknown',
                    status=status,
                    cpu_percent=proc.info.get('cpu_percent', 0) or 0,
                    memory_mb=memory_mb,
                    create_time=datetime.fromtimestamp(
                        proc.info.get('create_time', 0) or 0
                    ),
                    local_address="",
                    remote_address="",
                    connection_status="",
                    bytes_sent=bytes_sent,
                    bytes_recv=bytes_recv,
                )

                # Update history from cache
                if pid in self._process_cache:
                    cached = self._process_cache[pid]
                    dev_process.cpu_history = cached.cpu_history.copy()
                    dev_process.memory_history = cached.memory_history.copy()
                    dev_process.selected = cached.selected

                # Update metrics
                dev_process.update_metrics(dev_process.cpu_percent, memory_mb)

                # Apply service filter
                if service_filter and dev_process.service_type != service_filter:
                    continue

                # Apply status filter
                if status_filter and dev_process.status != status_filter:
                    continue

                # Apply search query
                if search_query:
                    query = search_query.lower()
                    searchable = f"{dev_process.name} {dev_process.cmdline} {dev_process.username}".lower()
                    if query not in searchable:
                        continue

                processes[pid] = dev_process
                self._process_cache[pid] = dev_process

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort: processes with ports first, then by name
        result = sorted(
            processes.values(),
            key=lambda p: (p.port == 0, p.service_type.value, p.name.lower())
        )
        return result

    def kill_process(
        self, process: PortProcess, force: bool = False
    ) -> tuple[bool, str]:
        """Kill a process. Returns (success, error_message)."""
        sig = signal.SIGKILL if force else signal.SIGTERM
        signal_name = "SIGKILL" if force else "SIGTERM"

        try:
            proc = psutil.Process(process.pid)

            # Check if process still exists
            if not proc.is_running():
                return False, "Process no longer exists"

            # Try to kill
            proc.send_signal(sig)

            # Wait a bit and check if it's gone
            try:
                proc.wait(timeout=2)
                success = True
                error = ""
            except psutil.TimeoutExpired:
                if not force:
                    # Try SIGKILL as fallback
                    proc.send_signal(signal.SIGKILL)
                    try:
                        proc.wait(timeout=2)
                        success = True
                        error = ""
                        signal_name = "SIGKILL"
                    except psutil.TimeoutExpired:
                        success = False
                        error = "Process did not terminate after SIGKILL"
                else:
                    success = False
                    error = "Process did not terminate"

        except psutil.NoSuchProcess:
            success = True
            error = ""
        except psutil.AccessDenied:
            success = False
            error = "Access denied - try running with sudo"
        except Exception as e:
            success = False
            error = str(e)

        # Record in history
        record = KillRecord(
            id=None,
            timestamp=datetime.now(),
            pid=process.pid,
            port=process.port,
            protocol=process.protocol,
            name=process.name,
            cmdline=process.cmdline,
            username=process.username,
            service_type=process.service_type.value,
            kill_signal=signal_name,
            success=success,
            error_message=error,
        )
        self.history_db.add_kill_record(record)

        # Remove from cache
        if process.pid in self._process_cache:
            del self._process_cache[process.pid]

        return success, error

    def kill_processes(
        self, processes: list[PortProcess], force: bool = False
    ) -> list[tuple[PortProcess, bool, str]]:
        """Kill multiple processes. Returns list of (process, success, error)."""
        results = []
        for proc in processes:
            success, error = self.kill_process(proc, force)
            results.append((proc, success, error))
        return results

    def kill_by_port(self, port: int, force: bool = False) -> list[tuple[PortProcess, bool, str]]:
        """Kill all processes on a specific port."""
        processes = self.get_port_processes(port_filter=port)
        return self.kill_processes(processes, force)

    def kill_by_service(
        self, service_type: ServiceType, force: bool = False
    ) -> list[tuple[PortProcess, bool, str]]:
        """Kill all processes of a specific service type."""
        processes = self.get_port_processes(service_filter=service_type)
        return self.kill_processes(processes, force)

    def get_system_stats(self) -> dict:
        """Get current system statistics."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024**3),
            "memory_total_gb": memory.total / (1024**3),
            "memory_available_gb": memory.available / (1024**3),
        }

    def get_selected_processes(self) -> list[PortProcess]:
        """Get all selected processes from cache."""
        return [p for p in self._process_cache.values() if p.selected]

    def toggle_selection(self, pid: int) -> bool:
        """Toggle selection state of a process. Returns new state."""
        if pid in self._process_cache:
            self._process_cache[pid].selected = not self._process_cache[pid].selected
            return self._process_cache[pid].selected
        return False

    def select_all(self, processes: list[PortProcess]):
        """Select all given processes."""
        for proc in processes:
            if proc.pid in self._process_cache:
                self._process_cache[proc.pid].selected = True
            proc.selected = True

    def deselect_all(self):
        """Deselect all processes."""
        for proc in self._process_cache.values():
            proc.selected = False

    def record_usage_snapshot(self):
        """Record current usage statistics."""
        processes = self.get_port_processes()
        stats = self.get_system_stats()

        unique_ports = len(set(p.port for p in processes))

        self.history_db.add_usage_snapshot(
            total_processes=len(processes),
            total_ports=unique_ports,
            cpu=stats["cpu_percent"],
            memory=stats["memory_percent"],
        )
