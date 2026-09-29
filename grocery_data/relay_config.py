"""Explicit non-secret transport configuration, shared by relay commands."""
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RelayTransport:
    ssh_host: str = "smako"
    container: str = "smako-scheduler-1"
    inbox: str = "/srv/app/var/raw_snapshots/source-inbox/willys"

    def __post_init__(self):
        for value in (self.ssh_host, self.container):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
                raise ValueError("Invalid relay host/container identifier")
        if not re.fullmatch(r"/[A-Za-z0-9_/-]+", self.inbox) or ".." in self.inbox:
            raise ValueError("Invalid relay inbox path")


def load_transport(path: Path | None) -> RelayTransport:
    if path is None:
        return RelayTransport()
    value = json.loads(path.read_bytes())
    if value.pop("schema", None) != "smako-relay-config-v1":
        raise ValueError("Unsupported relay configuration")
    return RelayTransport(**value)
