"""History and database models."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class KillRecord:
    """Record of a killed process."""

    id: Optional[int]
    timestamp: datetime
    pid: int
    port: int
    protocol: str
    name: str
    cmdline: str
    username: str
    service_type: str
    kill_signal: str  # SIGTERM or SIGKILL
    success: bool
    error_message: str = ""

    def to_tuple(self) -> tuple:
        """Convert to tuple for database insertion."""
        return (
            self.timestamp.isoformat(),
            self.pid,
            self.port,
            self.protocol,
            self.name,
            self.cmdline,
            self.username,
            self.service_type,
            self.kill_signal,
            self.success,
            self.error_message,
        )

    @classmethod
    def from_row(cls, row: tuple) -> "KillRecord":
        """Create from database row."""
        return cls(
            id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            pid=row[2],
            port=row[3],
            protocol=row[4],
            name=row[5],
            cmdline=row[6],
            username=row[7],
            service_type=row[8],
            kill_signal=row[9],
            success=bool(row[10]),
            error_message=row[11] if len(row) > 11 else "",
        )


class HistoryDB:
    """SQLite database for kill history."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        if db_path is None:
            db_dir = Path.home() / ".portkill"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "history.db"

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kill_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    port INTEGER NOT NULL,
                    protocol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    cmdline TEXT NOT NULL,
                    username TEXT NOT NULL,
                    service_type TEXT NOT NULL,
                    kill_signal TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    error_message TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON kill_history(timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_service_type
                ON kill_history(service_type)
            """)

            # Statistics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_processes INTEGER NOT NULL,
                    total_ports INTEGER NOT NULL,
                    cpu_usage REAL NOT NULL,
                    memory_usage REAL NOT NULL
                )
            """)

            conn.commit()

    def add_kill_record(self, record: KillRecord) -> int:
        """Add a kill record to history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO kill_history
                (timestamp, pid, port, protocol, name, cmdline, username,
                 service_type, kill_signal, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                record.to_tuple(),
            )
            conn.commit()
            return cursor.lastrowid

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        service_type: Optional[str] = None,
        success_only: bool = False,
    ) -> list[KillRecord]:
        """Get kill history with optional filters."""
        query = "SELECT * FROM kill_history WHERE 1=1"
        params: list = []

        if service_type:
            query += " AND service_type = ?"
            params.append(service_type)

        if success_only:
            query += " AND success = 1"

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return [KillRecord.from_row(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """Get statistics from history."""
        with sqlite3.connect(self.db_path) as conn:
            # Total kills
            total = conn.execute(
                "SELECT COUNT(*) FROM kill_history"
            ).fetchone()[0]

            # Success rate
            successful = conn.execute(
                "SELECT COUNT(*) FROM kill_history WHERE success = 1"
            ).fetchone()[0]

            # Kills by service type
            by_service = conn.execute("""
                SELECT service_type, COUNT(*) as count
                FROM kill_history
                GROUP BY service_type
                ORDER BY count DESC
            """).fetchall()

            # Kills today
            today = datetime.now().date().isoformat()
            today_count = conn.execute(
                "SELECT COUNT(*) FROM kill_history WHERE timestamp >= ?",
                (today,),
            ).fetchone()[0]

            # Most killed ports
            top_ports = conn.execute("""
                SELECT port, COUNT(*) as count
                FROM kill_history
                GROUP BY port
                ORDER BY count DESC
                LIMIT 5
            """).fetchall()

            return {
                "total_kills": total,
                "successful_kills": successful,
                "success_rate": (successful / total * 100) if total > 0 else 0,
                "kills_by_service": dict(by_service),
                "kills_today": today_count,
                "top_ports": dict(top_ports),
            }

    def add_usage_snapshot(
        self, total_processes: int, total_ports: int, cpu: float, memory: float
    ):
        """Add a usage statistics snapshot."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_stats
                (timestamp, total_processes, total_ports, cpu_usage, memory_usage)
                VALUES (?, ?, ?, ?, ?)
                """,
                (datetime.now().isoformat(), total_processes, total_ports, cpu, memory),
            )
            conn.commit()

    def get_usage_history(self, hours: int = 24) -> list[dict]:
        """Get usage history for the last N hours."""
        since = datetime.now().timestamp() - (hours * 3600)
        since_iso = datetime.fromtimestamp(since).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT timestamp, total_processes, total_ports, cpu_usage, memory_usage
                FROM usage_stats
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (since_iso,),
            )
            return [
                {
                    "timestamp": row[0],
                    "total_processes": row[1],
                    "total_ports": row[2],
                    "cpu_usage": row[3],
                    "memory_usage": row[4],
                }
                for row in cursor.fetchall()
            ]

    def clear_old_records(self, days: int = 30):
        """Clear records older than N days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM kill_history WHERE timestamp < ?", (cutoff_iso,)
            )
            conn.execute(
                "DELETE FROM usage_stats WHERE timestamp < ?", (cutoff_iso,)
            )
            conn.commit()
