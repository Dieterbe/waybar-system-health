import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .base import HealthCheckModule, HealthCheckResult, IgnoreRules, Status


@dataclass(frozen=True)
class MountThreshold:
    path: str
    warn_percent: float
    critical_percent: float

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("mountpoint path must be set")
        if not (0 <= self.warn_percent <= 100):
            raise ValueError(f"{self.path}: warn threshold must be between 0 and 100")
        if not (0 <= self.critical_percent <= 100):
            raise ValueError(f"{self.path}: critical threshold must be between 0 and 100")
        if self.warn_percent > self.critical_percent:
            raise ValueError(f"{self.path}: warn threshold cannot exceed critical threshold")


def load_mount_thresholds(path: str) -> List[MountThreshold]:
    """
    Load mount thresholds from JSON file.

    The file must contain a list of objects with `path`, `warn`, and `critical` keys.
    """
    cfg_path = Path(path)
    if not cfg_path.exists():
        return []

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Disk config '{path}' is not valid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Disk config '{path}' must be a JSON list of mount entries")

    mounts: List[MountThreshold] = []
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"Disk config '{path}' entry #{idx + 1} must be an object")
        mount_path = entry.get("path")
        warn = entry.get("warn")
        crit = entry.get("critical")
        if mount_path is None or warn is None or crit is None:
            raise ValueError(
                f"Disk config '{path}' entry #{idx + 1} must include 'path', 'warn', and 'critical'"
            )

        try:
            warn_val = float(warn)
            crit_val = float(crit)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Disk config '{path}' entry #{idx + 1}: warn/critical must be numbers"
            ) from exc

        mounts.append(MountThreshold(path=str(mount_path), warn_percent=warn_val, critical_percent=crit_val))

    return mounts


class DiskModule(HealthCheckModule):
    """Health check for disk usage across configured mountpoints."""

    def __init__(
        self,
        mount_thresholds: Optional[List[MountThreshold]] = None,
        ignore_rules: Optional[IgnoreRules] = None,
        config_error: Optional[str] = None,
    ):
        super().__init__(ignore_rules)
        self.mount_thresholds = mount_thresholds or []
        self.config_error = config_error

    def check(self) -> HealthCheckResult:
        if self.config_error:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[
                    "Disk usage: invalid configuration",
                    f"  {self.config_error}",
                ],
            )

        if not self.mount_thresholds:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[
                    "Disk usage: no mountpoints configured",
                    "Configure mounts in disk.json (see README)",
                ],
            )

        lines: List[str] = []
        mount_statuses: List[Status] = []

        for cfg in self.mount_thresholds:
            try:
                usage = shutil.disk_usage(cfg.path)
            except FileNotFoundError:
                mount_statuses.append(Status.WARN)
                lines.append(f"{cfg.path}: not found (warn)")
                continue
            except PermissionError:
                mount_statuses.append(Status.WARN)
                lines.append(f"{cfg.path}: permission denied")
                continue
            except OSError as exc:
                mount_statuses.append(Status.WARN)
                lines.append(f"{cfg.path}: error reading usage ({exc})")
                continue

            total = usage.total
            if total <= 0:
                mount_statuses.append(Status.WARN)
                lines.append(f"{cfg.path}: unable to determine size")
                continue

            used_percent = ((usage.total - usage.free) / usage.total) * 100

            if used_percent >= cfg.critical_percent:
                status = Status.CRITICAL
            elif used_percent >= cfg.warn_percent:
                status = Status.WARN
            else:
                status = Status.OK

            mount_statuses.append(status)

            free_gib = usage.free / (1024 ** 3)
            total_gib = usage.total / (1024 ** 3)
            marker = {
                Status.OK: "✓",
                Status.WARN: "!",
                Status.CRITICAL: "✗",
            }[status]
            lines.append(
                f"[{marker}] {cfg.path}: {used_percent:.1f}% used ({free_gib:.1f}/{total_gib:.1f} GiB free) "
                f"(warn {cfg.warn_percent:.1f}%, crit {cfg.critical_percent:.1f}%)"
            )

        overall_status = Status.worst(mount_statuses)
        return HealthCheckResult(status=overall_status, tooltipLines=lines)
