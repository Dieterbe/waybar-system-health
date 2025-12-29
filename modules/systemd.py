from typing import List, Optional
from .base import HealthCheckModule, IgnoreRules, Status, HealthCheckResult
from .utils import run, format_command_error


class SystemdModule(HealthCheckModule):
    """Health check for systemd system and user state."""

    def __init__(self, ignore_rules: Optional[IgnoreRules] = None):
        super().__init__(ignore_rules)
        self.max_tooltip_units = 10

    def _state_result(self, user: bool) -> HealthCheckResult:
        """Return HealthCheckResult describing systemd state."""
        label = " --user" if user else ""
        cmd = ["systemctl"]
        if user:
            cmd.append("--user")
        cmd += ["is-system-running"]
        code, out, err = run(cmd)

        if code == 127:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=["systemctl missing"],
            )

        state = (out.strip() or err.strip() or "unknown").splitlines()[0].strip()
        if state in ["degraded", "maintenance", "failed"]:
            status = Status.CRITICAL
        elif state in ["starting", "unknown"] or code >0:
            status = Status.WARN
        else:
            status = Status.OK

        return HealthCheckResult(
            status=status,
            tooltipLines=[f"systemd ({label}): {state}"],
        )

    def _failed_units_result(self, user: bool) -> HealthCheckResult:
        """Return HealthCheckResult describing failed units."""
        label = " --user" if user else ""
        cmd = ["systemctl"]
        if user:
            cmd.append("--user")
        cmd += ["--failed", "--no-legend", "--plain"]
        code, out, err = run(cmd)

        if code == 127:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[f"systemctl missing"],
            )
        if code != 0:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=format_command_error(f"systemctl{label} --failed", code, out, err),
            )

        units: List[str] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            unit = line.split()[0]
            if not self.is_ignored(unit):
                units.append(unit)

        if units:
            lines = [f"Failed units:"]
            for u in units[:self.max_tooltip_units]:
                lines.append(f"  • {u}")
            if len(units) > self.max_tooltip_units:
                lines.append(f"  … (+{len(units) - self.max_tooltip_units} more)")
            status = Status.CRITICAL
        else:
            lines = ["Failed units: none"]
            status = Status.OK

        return HealthCheckResult(status=status, tooltipLines=lines)

    def check(self) -> HealthCheckResult:
        """Check systemd health."""
        results = {
            "## System state": self._state_result(user=False),
            "## User state": self._state_result(user=True),
            "## Failed (system)": self._failed_units_result(user=False),
            "## Failed (user)": self._failed_units_result(user=True),
        }

        return HealthCheckResult.merge(results)
