"""Constants for PortKill."""

from enum import Enum


class ProcessStatus(str, Enum):
    """Status of a process."""

    RUNNING = "running"  # Processo rodando normalmente
    SLEEPING = "sleeping"  # Processo em espera (idle)
    STOPPED = "stopped"  # Processo parado (SIGSTOP)
    ZOMBIE = "zombie"  # Processo zumbi (encerrado mas não coletado)
    DEAD = "dead"  # Processo morto
    DISK_SLEEP = "disk_sleep"  # Esperando I/O (pode estar travado)
    IDLE = "idle"  # Idle (kernel thread)
    UNKNOWN = "unknown"  # Status desconhecido


# Status display info (label, color, icon) - Gruvbox colors
PROCESS_STATUS_INFO: dict[ProcessStatus, tuple[str, str, str]] = {
    ProcessStatus.RUNNING: ("Rodando", "#b8bb26", "●"),  # Gruvbox green
    ProcessStatus.SLEEPING: ("Idle", "#83a598", "○"),  # Gruvbox blue
    ProcessStatus.STOPPED: ("Parado", "#fabd2f", "■"),  # Gruvbox yellow
    ProcessStatus.ZOMBIE: ("Zumbi", "#fb4934", "✗"),  # Gruvbox red
    ProcessStatus.DEAD: ("Morto", "#fb4934", "✗"),  # Gruvbox red
    ProcessStatus.DISK_SLEEP: ("Travado", "#fe8019", "⚠"),  # Gruvbox orange
    ProcessStatus.IDLE: ("Idle", "#665c54", "○"),  # Gruvbox gray
    ProcessStatus.UNKNOWN: ("Desconhecido", "#665c54", "?"),  # Gruvbox gray
}


class ServiceType(str, Enum):
    """Types of services detected by command patterns."""

    NODE = "node"
    REACT = "react"
    PYTHON = "python"
    JAVA = "java"
    DOCKER = "docker"
    DATABASE = "database"
    WEB = "web"
    ELIXIR = "elixir"
    CPP = "cpp"
    RUST = "rust"
    GO = "go"
    SSH = "ssh"
    OTHER = "other"


# Patterns to detect service type from command
SERVICE_PATTERNS: dict[ServiceType, list[str]] = {
    ServiceType.NODE: ["node", "npm", "npx", "yarn", "pnpm", "bun"],
    ServiceType.REACT: ["react-scripts", "next", "vite", "webpack", "remix"],
    ServiceType.PYTHON: [
        "python",
        "python3",
        "flask",
        "uvicorn",
        "gunicorn",
        "django",
        "fastapi",
        "hypercorn",
    ],
    ServiceType.JAVA: ["java", "spring", "mvn", "gradle", "tomcat", "jetty"],
    ServiceType.DOCKER: ["docker", "dockerd", "containerd", "podman"],
    ServiceType.DATABASE: [
        "postgres",
        "postgresql",
        "mysql",
        "mysqld",
        "mongo",
        "mongod",
        "redis",
        "redis-server",
        "rabbitmq",
        "rabbit",
        "sqlite",
        "mariadb",
    ],
    ServiceType.WEB: ["nginx", "apache", "apache2", "httpd", "caddy", "traefik"],
    ServiceType.ELIXIR: ["beam", "beam.smp", "elixir", "mix", "phoenix", "erl"],
    ServiceType.CPP: ["a.out", "cmake", "make", "g++", "clang++"],
    ServiceType.RUST: ["cargo", "rustc", "target/debug", "target/release"],
    ServiceType.GO: ["go", "air", "gin"],
    ServiceType.SSH: ["ssh", "sshd", "ssh-agent"],
}

# Colors for each service type - Gruvbox colors
SERVICE_COLORS: dict[ServiceType, str] = {
    ServiceType.NODE: "#b8bb26",  # Gruvbox green
    ServiceType.REACT: "#8ec07c",  # Gruvbox aqua
    ServiceType.PYTHON: "#fabd2f",  # Gruvbox yellow
    ServiceType.JAVA: "#fb4934",  # Gruvbox red
    ServiceType.DOCKER: "#83a598",  # Gruvbox blue
    ServiceType.DATABASE: "#d3869b",  # Gruvbox purple
    ServiceType.WEB: "#83a598",  # Gruvbox blue
    ServiceType.ELIXIR: "#d3869b",  # Gruvbox purple
    ServiceType.CPP: "#8ec07c",  # Gruvbox aqua
    ServiceType.RUST: "#fe8019",  # Gruvbox orange
    ServiceType.GO: "#8ec07c",  # Gruvbox aqua
    ServiceType.SSH: "#fabd2f",  # Gruvbox yellow
    ServiceType.OTHER: "#a89984",  # Gruvbox fg4
}

# Known ports and their typical services
KNOWN_PORTS: dict[int, str] = {
    22: "SSH",
    80: "HTTP",
    443: "HTTPS",
    3000: "Node/React Dev",
    3001: "Node Dev",
    3306: "MySQL",
    4000: "Phoenix",
    5000: "Flask/Python",
    5173: "Vite",
    5432: "PostgreSQL",
    5672: "RabbitMQ",
    6379: "Redis",
    8000: "Django/FastAPI",
    8080: "HTTP Alt/Java",
    8443: "HTTPS Alt",
    8888: "Jupyter",
    9000: "PHP-FPM",
    15672: "RabbitMQ Management",
    27017: "MongoDB",
}

# Sparkline characters for charts
SPARKLINE_CHARS = " ▁▂▃▄▅▆▇█"

# Refresh intervals in seconds
REFRESH_INTERVALS = [1, 2, 5, 10, 30]
DEFAULT_REFRESH_INTERVAL = 2
