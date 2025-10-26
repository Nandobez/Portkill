"""Process tree screen."""

import psutil
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Footer, Static, Tree
from textual.widgets.tree import TreeNode
from rich.text import Text

from portkill.widgets.custom_header import AsciiHeader


class ProcessTreeScreen(Screen):
    """Screen showing process tree hierarchy."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "expand_all", "Expand All"),
        Binding("c", "collapse_all", "Collapse All"),
    ]

    DEFAULT_CSS = """
    ProcessTreeScreen {
        background: #282828;
    }

    #process-tree {
        height: 1fr;
        background: #282828;
        padding: 1;
    }

    #process-tree > .tree--guides {
        color: #504945;
    }

    #process-tree > .tree--cursor {
        background: #fe8019;
        color: #282828;
    }

    #process-tree:focus > .tree--cursor {
        background: #fe8019;
        color: #282828;
    }

    #stats-bar {
        height: 1;
        background: #3c3836;
        padding: 0 2;
    }
    """

    def __init__(self, root_pid: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.root_pid = root_pid  # If None, show all top-level processes

    def compose(self) -> ComposeResult:
        yield AsciiHeader()
        yield Tree("Processes", id="process-tree")
        yield Static("", id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the tree."""
        tree = self.query_one("#process-tree", Tree)
        tree.show_root = False
        tree.guide_depth = 4
        self._refresh_tree()

    def action_refresh(self) -> None:
        """Refresh tree."""
        self._refresh_tree()
        self.notify("Process tree refreshed")

    def action_expand_all(self) -> None:
        """Expand all nodes."""
        tree = self.query_one("#process-tree", Tree)
        tree.root.expand_all()

    def action_collapse_all(self) -> None:
        """Collapse all nodes."""
        tree = self.query_one("#process-tree", Tree)
        tree.root.collapse_all()

    def _refresh_tree(self) -> None:
        """Refresh process tree data."""
        tree = self.query_one("#process-tree", Tree)
        tree.clear()

        # Build process hierarchy
        processes = {}
        children = {}
        total_procs = 0

        for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cpu_percent', 'memory_info', 'status']):
            try:
                pid = proc.info['pid']
                ppid = proc.info['ppid']
                name = proc.info.get('name', 'unknown')
                cpu = proc.info.get('cpu_percent', 0) or 0
                mem_info = proc.info.get('memory_info')
                mem_mb = mem_info.rss / (1024 * 1024) if mem_info else 0
                status = proc.info.get('status', 'unknown')

                processes[pid] = {
                    'pid': pid,
                    'ppid': ppid,
                    'name': name,
                    'cpu': cpu,
                    'mem': mem_mb,
                    'status': status,
                }

                if ppid not in children:
                    children[ppid] = []
                children[ppid].append(pid)
                total_procs += 1

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Find root processes (those without parents or with init as parent)
        if self.root_pid:
            # Show specific process and its children
            root_pids = [self.root_pid] if self.root_pid in processes else []
        else:
            # Show only top-level dev processes for cleaner view
            dev_patterns = ['node', 'python', 'java', 'docker', 'npm', 'cargo', 'go']
            root_pids = []
            for pid, info in processes.items():
                name_lower = info['name'].lower()
                if any(pattern in name_lower for pattern in dev_patterns):
                    # Check if parent is not also a dev process
                    ppid = info['ppid']
                    if ppid in processes:
                        parent_name = processes[ppid]['name'].lower()
                        if not any(pattern in parent_name for pattern in dev_patterns):
                            root_pids.append(pid)
                    else:
                        root_pids.append(pid)

        # Build tree recursively
        def add_children(parent_node: TreeNode, pid: int, depth: int = 0):
            if depth > 10:  # Prevent infinite recursion
                return

            if pid not in children:
                return

            for child_pid in sorted(children[pid]):
                if child_pid not in processes:
                    continue

                info = processes[child_pid]
                label = self._format_process_label(info)
                child_node = parent_node.add(label, data=info)

                # Recursively add children
                add_children(child_node, child_pid, depth + 1)

        # Add root processes to tree
        for pid in sorted(root_pids):
            if pid not in processes:
                continue

            info = processes[pid]
            label = self._format_process_label(info)
            node = tree.root.add(label, data=info)

            # Add children
            add_children(node, pid)

        # Expand first level
        for child in tree.root.children:
            child.expand()

        # Update stats bar
        stats_bar = self.query_one("#stats-bar", Static)
        stats_text = Text()
        stats_text.append(f" Total processes: ", style="#a89984")
        stats_text.append(f"{total_procs}", style="bold #ebdbb2")
        stats_text.append(f"  │  Showing: ", style="#a89984")
        stats_text.append(f"{len(root_pids)}", style="bold #b8bb26")
        stats_text.append(f" trees", style="#a89984")
        stats_bar.update(stats_text)

    def _format_process_label(self, info: dict) -> Text:
        """Format a process label for the tree."""
        text = Text()

        # Status icon
        status = info.get('status', 'unknown')
        if status == 'running':
            text.append("● ", style="#b8bb26")
        elif status == 'sleeping':
            text.append("○ ", style="#83a598")
        elif status == 'zombie':
            text.append("✗ ", style="#fb4934")
        else:
            text.append("? ", style="#665c54")

        # Name
        text.append(f"{info['name']}", style="bold #ebdbb2")

        # PID
        text.append(f" [{info['pid']}]", style="#fabd2f")

        # CPU if significant
        cpu = info.get('cpu', 0)
        if cpu > 0.1:
            if cpu > 50:
                color = "#fb4934"
            elif cpu > 20:
                color = "#fabd2f"
            else:
                color = "#b8bb26"
            text.append(f" CPU:{cpu:.1f}%", style=color)

        # Memory if significant
        mem = info.get('mem', 0)
        if mem > 10:  # More than 10MB
            if mem > 500:
                color = "#fb4934"
            elif mem > 100:
                color = "#fabd2f"
            else:
                color = "#d3869b"

            if mem < 1024:
                text.append(f" MEM:{mem:.0f}MB", style=color)
            else:
                text.append(f" MEM:{mem/1024:.1f}GB", style=color)

        return text
