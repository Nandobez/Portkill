```
██████╗  ██████╗ ██████╗ ████████╗██╗  ██╗██╗██╗     ██╗
██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝██║ ██╔╝██║██║     ██║
██████╔╝██║   ██║██████╔╝   ██║   █████╔╝ ██║██║     ██║
██╔═══╝ ██║   ██║██╔══██╗   ██║   ██╔═██╗ ██║██║     ██║
██║     ╚██████╔╝██║  ██║   ██║   ██║  ██╗██║███████╗███████╗
╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝
```

# PortKill — Terminal Port & Process Manager

A TUI to inspect, kill and monitor the ports and processes a developer actually cares about. Built with Textual.

## Features

- **Live process table** with port, PID, command, CPU and memory.
- **One-key kill** (SIGTERM / SIGKILL) with confirmation.
- **Multi-select** for bulk operations.
- **Search & filter** by port, name or PID.
- **Auto-refresh** toggle.
- **Extra screens**: process tree, connections, docker, HTTP monitor, port scanner, history, heatmap, charts, logs.
- **CLI shortcuts** for quick one-shot actions.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Interactive TUI
portkill
# or the short alias
pk

# List ports in use
portkill --list

# Kill processes bound to a port
portkill --kill 3000

# Force kill (SIGKILL)
portkill --kill 3000 --force
```

## Shortcuts

| Key      | Action                         |
|----------|--------------------------------|
| `j` / `↓` | Move down                     |
| `k` / `↑` | Move up                       |
| `Space`  | Toggle selection               |
| `k`      | Kill (SIGTERM)                 |
| `K`      | Force kill (SIGKILL)           |
| `/`      | Search                         |
| `r`      | Toggle auto-refresh            |
| `h`      | History                        |
| `q`      | Quit                           |

## Project Layout

```
portkill/
├── pyproject.toml
├── portkill/
│   ├── app.py
│   ├── __main__.py
│   ├── screens/        # main, logs, docker, http_monitor, port_scanner,
│   │                   # process_tree, connections, graph, history, heatmap, ...
│   ├── widgets/        # process_table, filter_bar, details_panel, charts, header
│   ├── services/       # process_manager, alerts
│   ├── models/         # process, history
│   ├── styles/theme.tcss
│   └── utils/
└── tests/
```

## Requirements

- Python 3.10+
- Linux / macOS (uses `psutil`; ports listed via `/proc` and `lsof`-style probing)

## License

MIT.
