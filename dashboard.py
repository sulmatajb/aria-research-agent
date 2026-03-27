#!/usr/bin/env python3
"""ARIA Live Dashboard — real-time view of all agent activity."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import json
import db

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

db.init()
console = Console()

STATUS_STYLE = {
    'pending':     ('⏳', 'yellow'),
    'in_progress': ('🔄', 'cyan'),
    'done':        ('✅', 'green'),
    'failed':      ('❌', 'red'),
    'assigned':    ('📌', 'blue'),
}

AGENT_STYLE = {
    'supervisor':  ('🤖', 'magenta'),
    'perplexity':  ('🔍', 'blue'),
    'firecrawl':   ('🕷', 'cyan'),
    'synthesizer': ('✍️', 'green'),
    'telegram':    ('📱', 'yellow'),
}

TYPE_LABEL = {
    'user_request':       '📩 request',
    'search':             '🔍 search',
    'scrape':             '🕷  scrape',
    'synthesize':         '✍️  synthesis',
    'zotero_add':         '📚 zotero',
    'telegram_response':  '📱 response',
}


def short_payload(payload_raw):
    try:
        p = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
    except Exception:
        return str(payload_raw)[:50]
    desc = (p.get('query') or p.get('url') or p.get('message') or
            p.get('objective') or p.get('findings', '')[:40] or '')
    return str(desc)[:60]


def build_task_table(tasks):
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on dark_blue",
        border_style="dim blue",
        expand=True,
        title="[bold cyan]ARIA Task Queue[/bold cyan]",
        title_style="bold",
    )
    table.add_column("#",         style="dim", width=4, justify="right")
    table.add_column("Type",      width=16)
    table.add_column("Status",    width=14)
    table.add_column("Agent",     width=14)
    table.add_column("Description", ratio=1)
    table.add_column("Updated",   width=19, style="dim")

    for t in tasks:
        icon, style = STATUS_STYLE.get(t['status'], ('•', 'white'))
        agent_icon, _ = AGENT_STYLE.get(t.get('assigned_to', ''), ('', 'white'))
        type_label = TYPE_LABEL.get(t['type'], t['type'])
        desc = short_payload(t['payload'])
        updated = (t.get('updated_at') or t.get('created_at') or '')[-19:]

        table.add_row(
            str(t['id']),
            type_label,
            Text(f"{icon} {t['status']}", style=style),
            f"{agent_icon} {t.get('assigned_to') or '—'}",
            desc,
            updated,
        )

    return table


def build_log_table(logs):
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold white on dark_red",
        border_style="dim",
        expand=True,
        title="[bold red]Recent Logs[/bold red]",
        title_style="bold",
    )
    table.add_column("Time",   width=8,  style="dim")
    table.add_column("Agent",  width=12)
    table.add_column("Level",  width=7)
    table.add_column("Message", ratio=1)

    level_style = {'info': 'white', 'error': 'bold red', 'warn': 'yellow'}
    agent_colors = {
        'supervisor': 'magenta', 'perplexity': 'blue',
        'firecrawl': 'cyan', 'synthesizer': 'green', 'telegram': 'yellow'
    }
    for l in logs:
        ts = (l.get('created_at') or '')[-8:]
        color = agent_colors.get(l.get('agent', ''), 'white')
        lvl = l.get('level', 'info')
        table.add_row(
            ts,
            Text(l.get('agent', ''), style=color),
            Text(lvl, style=level_style.get(lvl, 'white')),
            l.get('message', ''),
        )

    return table


def build_stats_panel(tasks):
    total      = len(tasks)
    pending    = sum(1 for t in tasks if t['status'] == 'pending')
    active     = sum(1 for t in tasks if t['status'] == 'in_progress')
    done       = sum(1 for t in tasks if t['status'] == 'done')
    failed     = sum(1 for t in tasks if t['status'] == 'failed')

    content = (
        f"[yellow]⏳ Pending:[/yellow]    {pending:>3}\n"
        f"[cyan]🔄 Active:[/cyan]     {active:>3}\n"
        f"[green]✅ Done:[/green]       {done:>3}\n"
        f"[red]❌ Failed:[/red]     {failed:>3}\n"
        f"[dim]─────────────[/dim]\n"
        f"[white]Total:[/white]         {total:>3}"
    )
    return Panel(content, title="[bold]Stats[/bold]", border_style="dim blue", width=22)


def build_agents_panel():
    agents = [
        ('🤖', 'Supervisor',  'magenta'),
        ('🔍', 'Perplexity',  'blue'),
        ('🕷', 'Firecrawl',   'cyan'),
        ('✍️', 'Synthesizer', 'green'),
        ('📱', 'Telegram',    'yellow'),
    ]
    lines = '\n'.join(f"[{c}]{i} {n}[/{c}]" for i, n, c in agents)
    return Panel(lines, title="[bold]Agents[/bold]", border_style="dim blue", width=22)


def get_logs(limit=18):
    import sqlite3
    from db import DB_PATH
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def render():
    tasks = db.get_recent_tasks(30)
    active_tasks = [t for t in tasks if t['status'] in ('pending', 'in_progress')]
    recent_tasks = tasks[:20]
    logs  = get_logs(18)

    from rich.columns import Columns

    task_table = build_task_table(recent_tasks)
    log_table  = build_log_table(logs)
    stats      = build_stats_panel(tasks)
    agents_pan = build_agents_panel()

    header = Panel(
        Text.assemble(
            ("ARIA ", "bold cyan"),
            ("Autonomous Research Intelligence Assistant", "bold white"),
            ("   |   ", "dim"),
            (f"{len(active_tasks)} active", "bold yellow" if active_tasks else "dim"),
            ("   |   ", "dim"),
            ("Dissertation: Agentic AI for Residential Energy Management", "dim"),
        ),
        border_style="cyan",
        height=3,
    )

    side = Panel(
        Text.assemble(
            str(stats.renderable), "\n\n", str(agents_pan.renderable)
        ),
        border_style="dim",
    )

    layout = Layout()
    layout.split_column(
        Layout(header,     name="header",  size=3),
        Layout(name="body", ratio=1),
    )
    layout["body"].split_row(
        Layout(name="main", ratio=1),
        Layout(name="side", size=24),
    )
    layout["main"].split_column(
        Layout(task_table, name="tasks", ratio=3),
        Layout(log_table,  name="logs",  ratio=2),
    )
    layout["side"].update(
        Panel(
            Text.assemble(
                *[Text(f"{s.renderable}\n") for s in [stats, agents_pan]]
            ),
            border_style="dim blue",
        )
    )

    return layout


def main():
    print("📊 ARIA Dashboard starting…\n")
    from rich.columns import Columns

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        while True:
            try:
                tasks = db.get_recent_tasks(30)
                logs  = get_logs(18)
                active_tasks = [t for t in tasks if t['status'] in ('pending', 'in_progress')]
                recent_tasks = tasks[:20]

                header = Panel(
                    Text.assemble(
                        ("  ARIA  ", "bold white on dark_blue"),
                        ("  Autonomous Research Intelligence Assistant", "bold cyan"),
                        ("   ·   ", "dim"),
                        (
                            f"{len(active_tasks)} task(s) active",
                            "bold yellow" if active_tasks else "dim green"
                        ),
                        ("   ·   ", "dim"),
                        ("Besnik Sulmataj  ·  Westcliff DBA  ·  HEMS Dissertation", "dim"),
                    ),
                    border_style="blue",
                    height=3,
                )

                task_table = build_task_table(recent_tasks)
                log_table  = build_log_table(logs)
                stats      = build_stats_panel(tasks)
                agents_pan = build_agents_panel()

                layout = Layout()
                layout.split_column(
                    Layout(header,     name="header",  size=3),
                    Layout(name="body", ratio=1),
                )
                layout["body"].split_row(
                    Layout(name="main", ratio=1),
                    Layout(name="side", size=24),
                )
                layout["main"].split_column(
                    Layout(task_table, name="tasks", ratio=3),
                    Layout(log_table,  name="logs",  ratio=2),
                )
                layout["side"].split_column(
                    Layout(stats,      name="stats",  size=10),
                    Layout(agents_pan, name="agents", ratio=1),
                )

                live.update(layout)

            except KeyboardInterrupt:
                break
            except Exception as e:
                live.update(Panel(f"[red]Error: {e}[/red]"))

            time.sleep(2)


if __name__ == '__main__':
    main()
