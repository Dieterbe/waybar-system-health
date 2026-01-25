import re
from typing import List, Optional, Tuple
from .base import HealthCheckModule, IgnoreRules, Status, HealthCheckResult
from .utils import run, format_command_error
from .ux import format_status_line


class BtrfsModule(HealthCheckModule):
    """Health check for btrfs filesystem."""

    def __init__(self, ignore_rules: Optional[IgnoreRules] = None):
        super().__init__(ignore_rules)
        self.max_tooltip_lines = 12

    def detect_root_fstype(self) -> str:
        """Detect root filesystem type."""
        code, out, _ = run(["findmnt", "-n", "-o", "FSTYPE", "/"])
        if code == 0 and out.strip():
            return out.strip()
        code, out, _ = run(["stat", "-f", "-c", "%T", "/"])
        if code == 0 and out.strip():
            return out.strip()
        return "unknown"

    def device_stats(self) -> HealthCheckResult:
        """Get btrfs device stats."""
        code, out, err = run(["btrfs", "device", "stats", "/"])
        if code == 127:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[format_status_line(Status.WARN, "btrfs-progs missing")],
            )
        if code != 0:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=format_command_error("btrfs device stats", code, out, err),
            )

        nonzero = 0
        interesting: List[str] = []
        parse_err = False
        for ln in out.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            if self.is_ignored(ln):
                continue
            m = re.match(r"^\[.+\]\.(\S+)\s+(\d+)$", ln)
            if m:
                metric = m.group(1)
                val = int(m.group(2))
                if val != 0:
                    nonzero += 1
                    interesting.append(ln)
            else:
                parse_err = True
                interesting.append(f"couldn't parse this line: {ln}")

        if nonzero > 0:
            status = Status.CRITICAL
        elif parse_err:
            status = Status.WARN
        else:
            status = Status.OK

        details = [format_status_line(status, f"non-zero counters: {nonzero}")]
        for ln in interesting[:self.max_tooltip_lines]:
            details.append(f"  {ln}")

        return HealthCheckResult(
            status=status,
            tooltipLines=details,
        )

    def scrub_status(self) -> HealthCheckResult:
        """Get btrfs scrub status."""
        code, out, err = run(["sudo", "btrfs", "scrub", "status", "-R", "/"])
        if code == 127:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=["btrfs-progs missing"],
            )
        if code != 0:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=format_command_error("btrfs scrub status", code, out, err)
            )

        lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
        lines = [ln for ln in lines if not self.is_ignored(ln)]

        # Parse error counts from the output
        error_counts = {}
        for ln in lines:
            m = re.search(r"(\w+_errors?):\s*(\d+)", ln)
            if m:
                error_type = m.group(1)
                count = int(m.group(2))
                error_counts[error_type] = count

        # Determine status based on error counts
        total_errors = sum(error_counts.values())
        if total_errors > 0:
            status = Status.CRITICAL
        elif not error_counts: # we failed to parse out any errors
            status = Status.WARN
        else:
            status = Status.OK

        details = [format_status_line(status, f"scrub errors: {total_errors}" if error_counts else "unable to parse scrub output")]
        if error_counts:
            for error_type, count in sorted(error_counts.items()):
                if count > 0:
                    details.append(f" - {error_type}: {count}")

        return HealthCheckResult(
            status=status,
            tooltipLines=details,
        )

    def check(self) -> HealthCheckResult:
        """Check btrfs health."""
        fstype = self.detect_root_fstype()
        
        if fstype != "btrfs":
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[format_status_line(Status.WARN, f"(root is '{fstype}', not btrfs. check your config)")],
            )

        results = {
            "## Device stats": self.device_stats(),
            "## Scrub": self.scrub_status(),
        }

        return HealthCheckResult.merge(results)
