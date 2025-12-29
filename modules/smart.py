from dataclasses import dataclass
from itertools import chain
from typing import List, Optional, Tuple

from .base import HealthCheckModule, HealthCheckResult, IgnoreRules, Status
from .utils import format_command_error, run


@dataclass(frozen=True)
class SmartDevice:
    path: str
    device_type: Optional[str] = None


SMARTCTL_EXIT_BITS: List[Tuple[int, Status, str]] = [
    (1, Status.WARN, "smartctl: command line did not parse"),
    (2, Status.WARN, "smartctl: failed to open device"),
    (4, Status.WARN, "smartctl: SMART command failed"),
    (8, Status.CRITICAL, "SMART overall-health self-assessment reported failure"),
    (16, Status.CRITICAL, "At least one prefailure attribute is below threshold"),
    (32, Status.CRITICAL, "At least one usage attribute is below threshold"),
    (64, Status.CRITICAL, "SMART self-test log contains errors"),
    (128, Status.WARN, "A previous selective self-test is pending completion"),
]


def parse_scan_output(output: str) -> List[SmartDevice]:
    devices: List[SmartDevice] = []

    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if not line:
            continue

        tokens = line.split()
        if not tokens:
            continue

        path = tokens[0]
        device_type: Optional[str] = None
        if len(tokens) >= 3 and tokens[1] == "-d":
            device_type = tokens[2]

        devices.append(SmartDevice(path=path, device_type=device_type))

    return devices


class SmartModule(HealthCheckModule):
    """Health check for block devices using smartctl."""

    def __init__(self, ignore_rules: Optional[IgnoreRules] = None):
        super().__init__(ignore_rules)

    def check(self) -> HealthCheckResult:
        scan_code, scan_out, scan_err = run(["sudo", "smartctl", "--scan-open"])
        if scan_code == 127:
            return HealthCheckResult(
                status=Status.WARN,
                tooltipLines=[
                    "SMART: smartctl command not found",
                    "Install smartmontools to enable SMART health checks.",
                ],
            )

        devices = [dev for dev in parse_scan_output(scan_out) if not self.is_ignored(dev.path)]

        if not devices:
            lines = ["SMART: no devices detected via 'smartctl --scan-open'"]
            err_line = (scan_err.strip().splitlines() or [""])[0]
            if err_line:
                lines.append(f"  {err_line}")
            lines.append("Make sure your sudo permissions are set per the README.md")
            return HealthCheckResult(status=Status.WARN, tooltipLines=lines)

        results = [self._check_device(dev) for dev in devices]

        return HealthCheckResult(
            status=Status.worst([status for status, _ in results]),
            tooltipLines=list(chain.from_iterable(lines for _, lines in results)),
        )

    def _check_device(self, device: SmartDevice) -> Tuple[Status, List[str]]:
        cmd = ["sudo", "smartctl", "-a", device.path]
        code, out, err = run(cmd)
        if code == 127:
            return Status.WARN, [
                f"{device.path}: smartctl command not found (unexpected during check)"
            ]

        exit_messages = self._decode_exit_bits(code)
        health_line = self._extract_health_line(out) or self._extract_health_line(err)

        status = self._status_from_exit_and_health(exit_messages, health_line)
        summary = self._summarize_health(health_line, status)

        marker = {Status.OK: "✓", Status.WARN: "!", Status.CRITICAL: "✗"}[status]
        lines = [f"[{marker}] {device.path}: {summary}"]

        if exit_messages:
            for msg_status, msg in exit_messages:
                prefix = {
                    Status.OK: "info",
                    Status.WARN: "warn",
                    Status.CRITICAL: "crit",
                }[msg_status]
                lines.append(f"  - ({prefix}) {msg}")

        if code != 0 and not exit_messages and (err.strip() or not out.strip()):
            lines.extend(format_command_error("sudo smartctl -a", code, out, err))
        elif err.strip() and code == 0:
            lines.append("  stderr:")
            for ln in err.strip().splitlines():
                lines.append(f"    {ln}")

        return status, lines

    @staticmethod
    def _decode_exit_bits(code: int) -> List[Tuple[Status, str]]:
        lines: List[Tuple[Status, str]] = []
        for bit, status, message in SMARTCTL_EXIT_BITS:
            if code & bit:
                lines.append((status, message))
        return lines

    @staticmethod
    def _status_from_exit_and_health(
        exit_messages: List[Tuple[Status, str]],
        health_line: Optional[str],
    ) -> Status:
        statuses = [status for status, _ in exit_messages] or [Status.OK]

        if health_line:
            summary = health_line.lower()
            if any(keyword in summary for keyword in ["fail", "fault", "corrupt"]):
                statuses.append(Status.CRITICAL)
            elif any(keyword in summary for keyword in ["unknown", "n/a", "not supported"]):
                statuses.append(Status.WARN)
            elif any(keyword in summary for keyword in ["pass", "ok", "good"]):
                statuses.append(Status.OK)
            else:
                statuses.append(Status.WARN)

        return Status.worst(statuses)

    @staticmethod
    def _extract_health_line(text: str) -> Optional[str]:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            line_lower = stripped.lower()
            if "smart" in line_lower and (
                "health" in line_lower
                or "overall" in line_lower
                or "self-assessment" in line_lower
            ):
                return stripped
        return None

    @staticmethod
    def _summarize_health(health_line: Optional[str], status: Status) -> str:
        if health_line:
            return health_line
        return {
            Status.OK: "SMART status OK",
            Status.WARN: "SMART status uncertain",
            Status.CRITICAL: "SMART reports failure",
        }[status]
