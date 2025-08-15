"""Alerts service for monitoring process resources."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from enum import Enum


class AlertLevel(str, Enum):
    """Alert severity level."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents an alert."""
    id: str
    level: AlertLevel
    title: str
    message: str
    pid: int
    process_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    @property
    def color(self) -> str:
        """Get color for alert level."""
        colors = {
            AlertLevel.INFO: "#83a598",
            AlertLevel.WARNING: "#fabd2f",
            AlertLevel.CRITICAL: "#fb4934",
        }
        return colors.get(self.level, "#ebdbb2")

    @property
    def icon(self) -> str:
        """Get icon for alert level."""
        icons = {
            AlertLevel.INFO: "ℹ",
            AlertLevel.WARNING: "⚠",
            AlertLevel.CRITICAL: "🔴",
        }
        return icons.get(self.level, "?")


@dataclass
class AlertThresholds:
    """Configurable alert thresholds."""
    cpu_warning: float = 50.0  # CPU % for warning
    cpu_critical: float = 80.0  # CPU % for critical
    memory_warning: float = 500.0  # Memory MB for warning
    memory_critical: float = 1000.0  # Memory MB for critical
    connections_warning: int = 100  # Number of connections for warning
    connections_critical: int = 500  # Number of connections for critical


class AlertsService:
    """Service for monitoring and generating alerts."""

    def __init__(self, thresholds: AlertThresholds | None = None):
        self.thresholds = thresholds or AlertThresholds()
        self.alerts: list[Alert] = []
        self._alert_counter = 0
        self._callbacks: list[Callable[[Alert], None]] = []
        # Track which processes have already triggered alerts to avoid spam
        self._alerted_pids: dict[int, set[str]] = {}

    def on_alert(self, callback: Callable[[Alert], None]) -> None:
        """Register a callback for new alerts."""
        self._callbacks.append(callback)

    def check_process(self, pid: int, name: str, cpu: float, memory_mb: float, connections: int = 0) -> list[Alert]:
        """Check a process and generate alerts if thresholds exceeded."""
        new_alerts = []

        # Initialize tracking for this PID if needed
        if pid not in self._alerted_pids:
            self._alerted_pids[pid] = set()

        # Check CPU
        if cpu >= self.thresholds.cpu_critical:
            alert_key = "cpu_critical"
            if alert_key not in self._alerted_pids[pid]:
                alert = self._create_alert(
                    AlertLevel.CRITICAL,
                    f"High CPU: {name}",
                    f"Process {name} (PID: {pid}) is using {cpu:.1f}% CPU",
                    pid,
                    name
                )
                new_alerts.append(alert)
                self._alerted_pids[pid].add(alert_key)
        elif cpu >= self.thresholds.cpu_warning:
            alert_key = "cpu_warning"
            if alert_key not in self._alerted_pids[pid]:
                alert = self._create_alert(
                    AlertLevel.WARNING,
                    f"CPU Warning: {name}",
                    f"Process {name} (PID: {pid}) is using {cpu:.1f}% CPU",
                    pid,
                    name
                )
                new_alerts.append(alert)
                self._alerted_pids[pid].add(alert_key)
        else:
            # Clear CPU alerts if back to normal
            self._alerted_pids[pid].discard("cpu_critical")
            self._alerted_pids[pid].discard("cpu_warning")

        # Check Memory
        if memory_mb >= self.thresholds.memory_critical:
            alert_key = "mem_critical"
            if alert_key not in self._alerted_pids[pid]:
                alert = self._create_alert(
                    AlertLevel.CRITICAL,
                    f"High Memory: {name}",
                    f"Process {name} (PID: {pid}) is using {memory_mb:.0f}MB memory",
                    pid,
                    name
                )
                new_alerts.append(alert)
                self._alerted_pids[pid].add(alert_key)
        elif memory_mb >= self.thresholds.memory_warning:
            alert_key = "mem_warning"
            if alert_key not in self._alerted_pids[pid]:
                alert = self._create_alert(
                    AlertLevel.WARNING,
                    f"Memory Warning: {name}",
                    f"Process {name} (PID: {pid}) is using {memory_mb:.0f}MB memory",
                    pid,
                    name
                )
                new_alerts.append(alert)
                self._alerted_pids[pid].add(alert_key)
        else:
            # Clear memory alerts if back to normal
            self._alerted_pids[pid].discard("mem_critical")
            self._alerted_pids[pid].discard("mem_warning")

        # Check Connections
        if connections >= self.thresholds.connections_critical:
            alert_key = "conn_critical"
            if alert_key not in self._alerted_pids[pid]:
                alert = self._create_alert(
                    AlertLevel.CRITICAL,
                    f"High Connections: {name}",
                    f"Process {name} (PID: {pid}) has {connections} connections",
                    pid,
                    name
                )
                new_alerts.append(alert)
                self._alerted_pids[pid].add(alert_key)
        elif connections >= self.thresholds.connections_warning:
            alert_key = "conn_warning"
            if alert_key not in self._alerted_pids[pid]:
                alert = self._create_alert(
                    AlertLevel.WARNING,
                    f"Connection Warning: {name}",
                    f"Process {name} (PID: {pid}) has {connections} connections",
                    pid,
                    name
                )
                new_alerts.append(alert)
                self._alerted_pids[pid].add(alert_key)
        else:
            # Clear connection alerts if back to normal
            self._alerted_pids[pid].discard("conn_critical")
            self._alerted_pids[pid].discard("conn_warning")

        # Trigger callbacks for new alerts
        for alert in new_alerts:
            for callback in self._callbacks:
                callback(alert)

        return new_alerts

    def _create_alert(self, level: AlertLevel, title: str, message: str, pid: int, name: str) -> Alert:
        """Create a new alert."""
        self._alert_counter += 1
        alert = Alert(
            id=f"alert_{self._alert_counter}",
            level=level,
            title=title,
            message=message,
            pid=pid,
            process_name=name,
        )
        self.alerts.append(alert)
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        return alert

    def get_unacknowledged(self) -> list[Alert]:
        """Get all unacknowledged alerts."""
        return [a for a in self.alerts if not a.acknowledged]

    def acknowledge(self, alert_id: str) -> None:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                break

    def acknowledge_all(self) -> None:
        """Acknowledge all alerts."""
        for alert in self.alerts:
            alert.acknowledged = True

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self.alerts = []
        self._alerted_pids = {}

    def cleanup_pid(self, pid: int) -> None:
        """Clean up tracking for a terminated process."""
        if pid in self._alerted_pids:
            del self._alerted_pids[pid]
