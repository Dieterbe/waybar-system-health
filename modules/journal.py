from typing import List, Optional, Tuple
from .base import HealthCheckModule, IgnoreRules, Status, HealthCheckResult
from .utils import run


class JournalModule(HealthCheckModule):
    """Health check for systemd journal errors."""

    def __init__(self, ignore_rules: Optional[IgnoreRules] = None):
        super().__init__(ignore_rules)
        self.max_tooltip_lines = 15

    def check(self) -> HealthCheckResult:
        """Check journal health."""
        cmd = ["journalctl", "-b", "-p", "err..emerg", "--no-pager", "-o", "short-iso"]
        code, out, err = run(cmd)
        if code == 127:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=["journalctl missing"],
            )
        if code != 0 and not out.strip():
            note = (err.strip() or "cannot read journal").splitlines()[0] # TODO don't just use the first line only
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=["Journal errors (err..emerg): (not readable)", f"  {note}", "", "Tip: add user to systemd-journal group, then re-login."],
            )

        lines_all = [ln for ln in out.splitlines() if ln.strip()]
        lines_filtered = [ln for ln in lines_all if not self.is_ignored(ln)]

        count = len(lines_filtered)
        recent = lines_filtered[-self.max_tooltip_lines:]

        if count == 0:
            return HealthCheckResult(
                status=Status.OK,
                tooltipLines=["No errors found in journal"],
            )

        details: List[str] = []
        details.append(f"Journal errors (err..emerg): {count}")
        if recent:
            details.append("")
            details.append("Most recent:")
            for ln in recent:
                details.append(f"  {ln}")
            if count > len(recent):
                details.append(f"  … (+{count - len(recent)} more)")

        return HealthCheckResult(
            status=Status.CRITICAL,
            tooltipLines=details,
        )
