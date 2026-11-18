"""Calendar retention: an archive may satisfy several rules, but is kept once."""

from dataclasses import dataclass
from datetime import date, datetime
import re

LEGACY = re.compile(r"Samba_Backup_(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})(\d*)\.tar\Z")
CURRENT = re.compile(
    r"AutoBackup_([a-f0-9]{12})_(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_([a-f0-9]{8})\.tar\Z"
)


@dataclass(frozen=True)
class Archive:
    name: str
    timestamp: datetime
    size: int
    sequence: int = 0
    modified: float = 0


def parse_archive(name: str, size: int, modified: float = 0) -> Archive | None:
    if size <= 0:
        return None
    legacy, current = LEGACY.fullmatch(name), CURRENT.fullmatch(name)
    try:
        if legacy:
            return Archive(
                name,
                datetime(*(int(v) for v in legacy.groups()[:5])),
                size,
                int(legacy.group(6) or 0),
                modified,
            )
        if current:
            return Archive(
                name,
                datetime(*(int(v) for v in current.groups()[1:7])),
                size,
                int(current.group(8), 16),
                modified,
            )
    except ValueError:
        pass
    return None


def make_plan(
    archives: list[Archive],
    today: date,
    daily: int = 7,
    weekly: int = 4,
    monthly: int = 2,
) -> dict:
    if min(daily, weekly, monthly) < 1 or not archives:
        raise ValueError(
            "A positive retention and at least one valid backup are required"
        )
    if any(a.timestamp.date() > today for a in archives):
        raise ValueError("Future backup date: deletion forbidden")
    by_day = {}
    for item in sorted(
        archives, key=lambda a: (a.timestamp, a.modified, a.sequence, a.name)
    ):
        by_day[item.timestamp.date()] = item
    days = sorted(by_day, reverse=True)
    sundays = [day for day in days if day.weekday() == 6]
    first = {}
    for day in sorted(sundays):
        first.setdefault((day.year, day.month), day)
    groups = {
        "daily": days[:daily],
        "weekly": sundays[:weekly],
        "monthly": [first[m] for m in sorted(first, reverse=True)[:monthly]],
    }
    selected = set().union(*(set(values) for values in groups.values()))
    keep = {by_day[day].name for day in selected}
    return {
        "keep": sorted(keep),
        "delete": sorted(a.name for a in archives if a.name not in keep),
        "latest": by_day[days[0]].name,
        "latest_timestamp": by_day[days[0]].timestamp.isoformat(),
        "roles": {
            by_day[d].name: [k for k, dates in groups.items() if d in dates]
            for d in selected
        },
        **{key: [by_day[d].name for d in dates] for key, dates in groups.items()},
    }
