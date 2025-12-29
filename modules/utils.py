import subprocess
import re
from pathlib import Path
from typing import List, Tuple, Dict
from .base import IgnoreRules


def run(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, text=True, capture_output=True)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"


def format_command_error(cmd_name: str, code: int, stdout: str, stderr: str) -> List[str]:
    """Format a command error with exit code and output.
    
    Args:
        cmd_name: Name of the command that failed
        code: Exit code
        stdout: Standard output from the command
        stderr: Standard error from the command
        
    Returns:
        List of formatted error lines
    """
    lines = [f"{cmd_name} failed with code {code}"]
    
    if stderr.strip():
        lines.append("stderr:")
        for ln in stderr.strip().splitlines():
            lines.append(f"  {ln}")
    
    if stdout.strip():
        lines.append("stdout:")
        for ln in stdout.strip().splitlines():
            lines.append(f"  {ln}")
    
    return lines


def parse_ignore_file(path: str, known_modules: List[str]) -> Dict[str, IgnoreRules]:
    """
    Parse ignore file and return dict of IgnoreRules by module.
    
    File format: lines of the form 'module:<regex>'.
    Lines starting with '#' or empty lines are ignored.
    
    Args:
        path: Path to the ignore file
        known_modules: List of valid module names.
    
    Returns:
        Dict mapping module names to IgnoreRules
    
    Raises:
        ValueError: If a line specifies an unknown module or doesn't match expected format
    """
    rules_by_module: Dict[str, List[re.Pattern]] = {}
    p = Path(path)
    
    if not p.exists():
        return {}

    for line_num, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        m = re.match(r"^(\w+):(.+)$", line)
        if not m:
            raise ValueError(f"Line {line_num}: Invalid format '{line}'. Expected 'module:<regex>'")
        
        module = m.group(1).strip()
        pattern = m.group(2).strip()
        
        if module not in known_modules:
            raise ValueError(f"Line {line_num}: Unknown module '{module}'. Known modules: {', '.join(known_modules)}")
        
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Line {line_num}: Invalid regex pattern '{pattern}': {e}")

        if module not in rules_by_module:
            rules_by_module[module] = []
        rules_by_module[module].append(compiled)

    return {module: IgnoreRules(patterns) for module, patterns in rules_by_module.items()}
