import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .base import HealthCheckModule, HealthCheckResult, IgnoreRules, Status
from .ux import format_status_line


@dataclass(frozen=True)
class LogseqGraphConfig:
    path: Path
    label: Optional[str] = None

    def display_name(self) -> str:
        return self.label or str(self.path)


def load_logseq_graphs(path: str) -> List["LogseqGraphConfig"]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return []

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Logseq config '{path}' is not valid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Logseq config '{path}' must be a JSON list of graph entries")

    graphs: List[LogseqGraphConfig] = []
    for idx, entry in enumerate(data):
        label: Optional[str]
        if isinstance(entry, str):
            graph_path = entry
            label = None
        elif isinstance(entry, dict):
            graph_path = entry.get("path")
            label_raw = entry.get("label")
            label = str(label_raw) if label_raw is not None else None
        else:
            raise ValueError(
                f"Logseq config '{path}' entry #{idx + 1} must be a string path or an object with a 'path' field"
            )

        if not graph_path:
            raise ValueError(
                f"Logseq config '{path}' entry #{idx + 1} must include a non-empty 'path'"
            )

        graphs.append(
            LogseqGraphConfig(
                path=Path(str(graph_path)).expanduser(),
                label=label,
            )
        )

    return graphs


class LogseqModule(HealthCheckModule):
    """Detect Logseq sync conflicts."""

    def __init__(
        self,
        graph_roots: Optional[List[LogseqGraphConfig]] = None,
        ignore_rules: Optional[IgnoreRules] = None,
        config_error: Optional[str] = None,
    ):
        super().__init__(ignore_rules)
        self.graph_roots = graph_roots or []
        self.config_error = config_error
        self.max_conflict_lines = 10

    def check(self) -> HealthCheckResult:
        if self.config_error:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[
                    format_status_line(Status.WARN, "Logseq: invalid configuration"),
                    f"  {self.config_error}",
                ],
            )

        if not self.graph_roots:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[
                    format_status_line(Status.WARN, "Logseq: no graphs configured"),
                    "Add paths in logseq.json (see README)",
                ],
            )

        lines: List[str] = []
        statuses: List[Status] = []

        for cfg in self.graph_roots:
            label = cfg.display_name()
            if not cfg.path.exists():
                statuses.append(Status.WARN)
                lines.append(format_status_line(Status.WARN, f"{label}: path does not exist"))
                continue
            if not cfg.path.is_dir():
                statuses.append(Status.WARN)
                lines.append(format_status_line(Status.WARN, f"{label}: path is not a directory"))
                continue

            conflicts, error = self._find_conflicts(cfg.path)
            if error:
                statuses.append(Status.WARN)
                lines.append(format_status_line(Status.WARN, f"{label}: error scanning graph"))
                lines.append(f"  {error}")
                continue

            if conflicts:
                statuses.append(Status.CRITICAL)
                lines.append(format_status_line(Status.CRITICAL, f"{label}: sync conflicts detected ({len(conflicts)})"))
                for conflict in conflicts[: self.max_conflict_lines]:
                    lines.append(f"  - {self._format_conflict(cfg.path, conflict)}")
                if len(conflicts) > self.max_conflict_lines:
                    lines.append(
                        f"  … (+{len(conflicts) - self.max_conflict_lines} more)"
                    )
            else:
                statuses.append(Status.OK)
                lines.append(format_status_line(Status.OK, f"{label}: no sync conflicts"))

        overall = Status.worst(statuses)
        return HealthCheckResult(status=overall, tooltipLines=lines)

    def _find_conflicts(self, graph_root: Path) -> Tuple[List[Path], Optional[str]]:
        conflicts: List[Path] = []
        try:
            for candidate in graph_root.rglob("*sync-conflict*"):
                if not candidate.is_file():
                    continue
                if self.is_ignored(str(candidate)):
                    continue
                conflicts.append(candidate)
        except OSError as exc:
            return [], str(exc)

        return conflicts, None

    @staticmethod
    def _format_conflict(graph_root: Path, conflict: Path) -> str:
        try:
            relative = conflict.relative_to(graph_root)
            return str(relative)
        except ValueError:
            return str(conflict)
