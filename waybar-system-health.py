#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict, Any

from modules.utils import parse_ignore_file
from modules.systemd import SystemdModule
from modules.journal import JournalModule
from modules.btrfs import BtrfsModule
from modules.disk import DiskModule, load_mount_thresholds
from modules.smart import SmartModule
from modules.logseq import LogseqModule, load_logseq_graphs
from modules.base import Status, HealthCheckResult


STATUS_ICONS = {
    Status.OK: "✓",
    Status.WARN: "",
    Status.CRITICAL: "",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Waybar system health reporter")
    parser.add_argument(
        "--format",
        choices=["waybar", "hyprpanel"],
        default="waybar",
        help="Selects the status JSON schema.",
    )
    return parser.parse_args()

def get_config_dir() -> Path:
    """Get the config directory following XDG Base Directory spec."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home)
    return Path.home() / ".config"

def main() -> None:
    args = parse_args()
    ignore_rules = parse_ignore_file(
        os.environ.get(
            "WAYBAR_SYSTEM_HEALTH_IGNORE",
            str(get_config_dir() / "waybar-system-health" / "ignore")
        ),
        ["unit", "journal", "btrfs", "disk", "smart", "logseq"]
    )

    disk_config_path = os.environ.get(
        "WAYBAR_SYSTEM_HEALTH_DISK",
        str(get_config_dir() / "waybar-system-health" / "disk.json"),
    )
    disk_thresholds = []
    disk_config_error = None
    try:
        disk_thresholds = load_mount_thresholds(disk_config_path)
    except ValueError as exc:
        disk_config_error = str(exc)

    logseq_config_path = str(get_config_dir() / "waybar-system-health" / "logseq.json")
    logseq_graphs = []
    logseq_config_error = None
    try:
        logseq_graphs = load_logseq_graphs(logseq_config_path)
    except ValueError as exc:
        logseq_config_error = str(exc)

    modules = {
        "Units": SystemdModule(ignore_rules=ignore_rules.get("unit")),
        "Journal": JournalModule(ignore_rules=ignore_rules.get("journal")),
        "Btrfs": BtrfsModule(ignore_rules=ignore_rules.get("btrfs")),
        "Disk": DiskModule(
            mount_thresholds=disk_thresholds,
            ignore_rules=ignore_rules.get("disk"),
            config_error=disk_config_error,
        ),
        "SMART": SmartModule(ignore_rules=ignore_rules.get("smart")),
        "Logseq": LogseqModule(
            graph_roots=logseq_graphs,
            ignore_rules=ignore_rules.get("logseq"),
            config_error=logseq_config_error,
        ),
    }
    results = {name: m.check() for name, m in modules.items()}
    merged = HealthCheckResult.merge({f"# {name}": result for name, result in results.items()})

    if args.format == "hyprpanel":
        print(json.dumps(json_hyprpanel(results, merged)))
    else:
        print(json.dumps(json_waybar(results, merged)))

def json_hyprpanel(results: Dict[str, HealthCheckResult], merged: HealthCheckResult) -> str:
    text = STATUS_ICONS[Status.OK]
    if merged.status != Status.OK:
        text = " ".join([
            f"{STATUS_ICONS.get(result.status, result.status.value)}  {name}"
            for name, result in results.items()
            if result.status != Status.OK
        ])

    tooltip = "\n".join(merged.tooltipLines)
    return {
        "icon": STATUS_ICONS[merged.status],
        "label": text,
        "tooltip": tooltip,
        "class": merged.status.value,
    }    

def json_waybar(results: Dict[str, HealthCheckResult], merged: HealthCheckResult):
    text = STATUS_ICONS[Status.OK]
    if merged.status != Status.OK:
        text = " ".join([
            f"{name}:{STATUS_ICONS.get(result.status, result.status.value)}"
            for name, result in results.items()
            if result.status != Status.OK
        ])

    tooltip = "\n".join(merged.tooltipLines)
    return {
        "text": text,
        "tooltip": tooltip, 
        "class": merged.status.value, 
        "percentage": 100 if merged.status == Status.OK else 0
    }

if __name__ == "__main__":
    main()
