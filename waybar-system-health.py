#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Dict, Any

from modules.utils import parse_ignore_file
from modules.systemd import SystemdModule
from modules.journal import JournalModule
from modules.btrfs import BtrfsModule
from modules.disk import DiskModule, load_mount_thresholds
from modules.base import Status, HealthCheckResult

def get_config_dir() -> Path:
    """Get the config directory following XDG Base Directory spec."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home)
    return Path.home() / ".config"

def main() -> None:
    ignore_rules = parse_ignore_file(
        os.environ.get(
            "WAYBAR_SYSTEM_HEALTH_IGNORE",
            str(get_config_dir() / "waybar-system-health" / "ignore")
        ),
        ["unit", "journal", "btrfs", "disk"]
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

    modules = {
        "Units": SystemdModule(ignore_rules=ignore_rules.get("unit")),
        "Journal": JournalModule(ignore_rules=ignore_rules.get("journal")),
        "Btrfs": BtrfsModule(ignore_rules=ignore_rules.get("btrfs")),
        "Disk": DiskModule(
            mount_thresholds=disk_thresholds,
            ignore_rules=ignore_rules.get("disk"),
            config_error=disk_config_error,
        ),
    }
    results = {name: m.check() for name, m in modules.items()}

    merged = HealthCheckResult.merge({f"# {name}": result for name, result in results.items()})

    if merged.status == Status.OK:
        text = "✓"
    else:
        non_ok_statuses = [f"{name}:{result.status.value}" for name, result in results.items() if result.status != Status.OK]
        text = f"⚠ {' '.join(non_ok_statuses)}"

    tooltip = "\n".join(merged.tooltipLines)

    payload = {"text": text, "tooltip": tooltip, "class": merged.status.value}
    print(json.dumps(payload))

if __name__ == "__main__":
    main()