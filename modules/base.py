from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum
import re


class Status(Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"

    @staticmethod
    def worst(statuses: List["Status"]) -> "Status":
        order = {Status.OK: 0, Status.WARN: 1, Status.CRITICAL: 2}
        return max(statuses, key=lambda s: order.get(s, 0))


@dataclass
class IgnoreRules:
    patterns: List[re.Pattern]

@dataclass
class HealthCheckResult:
    status: Status
    tooltipLines: List[str]
    
    @staticmethod
    def merge(results: Dict[str, "HealthCheckResult"]) -> "HealthCheckResult":
        """Merge multiple HealthCheckResults into a single result.
        
        Args:
            results: Dict mapping module names to their HealthCheckResults
            
        Returns:
            A merged HealthCheckResult with the worst status and combined tooltip lines
        """
        merged_lines = []
        for name, result in results.items():
            if merged_lines:
                merged_lines.append("")
            merged_lines.append(f"{name}:")
            merged_lines.extend(result.tooltipLines)
        
        return HealthCheckResult(
            status=Status.worst([r.status for r in results.values()]),
            tooltipLines=merged_lines,
        )

class HealthCheckModule(ABC):
    def __init__(self, ignore_rules: Optional[IgnoreRules] = None):
        self.ignore_rules = ignore_rules or IgnoreRules(patterns=[])

    @abstractmethod
    def check(self) -> HealthCheckResult:
        pass

    def is_ignored(self, text: str) -> bool:
        return any(r.search(text) for r in self.ignore_rules.patterns)
