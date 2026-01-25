from .base import Status

STATUS_ICONS = {
    Status.OK: "✓",
    Status.WARN: "",
    Status.CRITICAL: "✗",
}

def status_icon(status: Status) -> str:
    return STATUS_ICONS.get(status, "")

def format_status_line(status: Status, message: str) -> str:
    icon = status_icon(status)
    return f"{icon} {message}"