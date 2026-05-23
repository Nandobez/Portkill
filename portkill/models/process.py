"""Process and Port models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from portkill.utils.constants import (
    ProcessStatus,
    ServiceType,
    SERVICE_PATTERNS,
    PROCESS_STATUS_INFO,
    SERVICE_COLORS,
)


@dataclass
class PortProcess:
    """Represents a process with an open port."""

    pid: int
    port: int
    protocol: str  # TCP or UDP
    name: str
    cmdline: str
    username: str
    status: ProcessStatus
    cpu_percent: float
    memory_mb: float
    create_time: datetime
    local_address: str
    remote_address: str = ""
    connection_status: str = ""  # LISTEN, ESTABLISHED, etc.
    service_type: ServiceType = field(default=ServiceType.OTHER)
    selected: bool = False
    cpu_history: list[float] = field(default_factory=list)
    memory_history: list[float] = field(default_factory=list)
    # Network I/O
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    connections_count: int = 0

    def __post_init__(self):
        """Detect service type from command line."""
        if self.service_type == ServiceType.OTHER:
            self.service_type = self._detect_service_type()

    def _detect_service_type(self) -> ServiceType:
        """Detect the service type based on command line patterns."""
        cmd_lower = self.cmdline.lower()
        name_lower = self.name.lower()

        for service_type, patterns in SERVICE_PATTERNS.items():
            for pattern in patterns:
                if pattern in cmd_lower or pattern in name_lower:
                    return service_type

        return ServiceType.OTHER

    @property
    def color(self) -> str:
        """Get the color for this service type."""
        return SERVICE_COLORS.get(self.service_type, "white")

    @property
    def status_info(self) -> tuple[str, str, str]:
        """Get status display info (label, color, icon)."""
        return PROCESS_STATUS_INFO.get(
            self.status, ("Desconhecido", "dim", "?")
        )

    @property
    def status_icon(self) -> str:
        """Get the status icon."""
        return self.status_info[2]

    @property
    def status_color(self) -> str:
        """Get the status color."""
        return self.status_info[1]

    @property
    def status_label(self) -> str:
        """Get the status label."""
        return self.status_info[0]

    @property
    def uptime(self) -> str:
        """Get human-readable uptime."""
        delta = datetime.now() - self.create_time
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            return f"{days}d{hours}h"

    @property
    def memory_display(self) -> str:
        """Get human-readable memory usage."""
        if self.memory_mb < 1:
            return f"{self.memory_mb * 1024:.0f}KB"
        elif self.memory_mb < 1024:
            return f"{self.memory_mb:.1f}MB"
        else:
            return f"{self.memory_mb / 1024:.2f}GB"

    @property
    def short_command(self) -> str:
        """Get shortened command for display."""
        max_len = 300
        if len(self.cmdline) <= max_len:
            return self.cmdline
        return self.cmdline[: max_len - 3] + "..."

    @property
    def network_io_display(self) -> str:
        """Get human-readable network I/O."""
        return f"↑{self._format_bytes(self.bytes_sent)} ↓{self._format_bytes(self.bytes_recv)}"

    @staticmethod
    def _format_bytes(bytes_val: int) -> str:
        """Format bytes to human-readable string."""
        if bytes_val < 1024:
            return f"{bytes_val}B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f}KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f}MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.2f}GB"

    def update_metrics(self, cpu: float, memory: float):
        """Update CPU and memory metrics, keeping history."""
        max_history = 60  # Keep 60 data points

        self.cpu_percent = cpu
        self.memory_mb = memory

        self.cpu_history.append(cpu)
        self.memory_history.append(memory)

        if len(self.cpu_history) > max_history:
            self.cpu_history = self.cpu_history[-max_history:]
        if len(self.memory_history) > max_history:
            self.memory_history = self.memory_history[-max_history:]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "pid": self.pid,
            "port": self.port,
            "protocol": self.protocol,
            "name": self.name,
            "cmdline": self.cmdline,
            "username": self.username,
            "status": self.status.value,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "create_time": self.create_time.isoformat(),
            "local_address": self.local_address,
            "remote_address": self.remote_address,
            "connection_status": self.connection_status,
            "service_type": self.service_type.value,
        }
