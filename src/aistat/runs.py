"""Analysis run folders and the run state machine."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import __version__
from .audit import now_iso
from .errors import InvalidState

TERMINAL = {"EXPORTED", "CANCELLED"}

TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"IMPORTED"},
    "IMPORTED": {"PROFILED"},
    "PROFILED": {"PLAN_DRAFTED"},
    "PLAN_DRAFTED": {"JEV_GATE_A", "BLOCKED"},
    "JEV_GATE_A": {"BLOCKED", "USER_APPROVAL"},
    "BLOCKED": {"JEV_GATE_A"},
    "USER_APPROVAL": {"EXECUTING"},
    "EXECUTING": {"EXECUTED", "FAILED"},
    "FAILED": {"EXECUTING"},
    "EXECUTED": {"JEV_GATE_B"},
    "JEV_GATE_B": {"EXECUTED", "REPORT_GENERATED"},
    "REPORT_GENERATED": {"EXPORTED"},
    "EXPORTED": set(),
    "CANCELLED": set(),
}

RUN_ID = re.compile(r"^RUN_(\d{8})_(\d{3})$")


class Run:
    def __init__(self, path: Path):
        self.dir = path
        self.manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))

    @classmethod
    def create(cls, runs_root: Path, dataset: dict) -> "Run":
        today = datetime.now().strftime("%Y%m%d")
        used = [int(m.group(2)) for p in runs_root.iterdir() if (m := RUN_ID.match(p.name)) and m.group(1) == today]
        n = max(used, default=0) + 1
        while True:
            run_id = f"RUN_{today}_{n:03d}"
            try:
                (runs_root / run_id).mkdir()
                break
            except FileExistsError:
                n += 1
        path = runs_root / run_id
        manifest = {
            "run_id": run_id,
            "aistat_version": __version__,
            "created_at": now_iso(),
            "status": "CREATED",
            "history": [{"state": "CREATED", "ts": now_iso()}],
            "dataset": dataset,
            "method": None,
            "engine": None,
            "confirmations": [],
            "outputs": {},
        }
        (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (path / "execution_log.json").write_text("[]", encoding="utf-8")
        run = cls(path)
        run.log("run_created", dataset_id=dataset["id"])
        return run

    # ---- state -----------------------------------------------------------

    @property
    def id(self) -> str:
        return self.manifest["run_id"]

    @property
    def status(self) -> str:
        return self.manifest["status"]

    @property
    def history(self) -> list[dict]:
        return self.manifest["history"]

    @property
    def confirmations(self) -> list[dict]:
        return self.manifest["confirmations"]

    def set_status(self, state: str, **info) -> None:
        if state == self.status:
            return
        allowed = TRANSITIONS[self.status] | ({"CANCELLED"} if self.status not in TERMINAL else set())
        if state not in allowed:
            raise InvalidState(f"{self.id} 目前狀態 {self.status}，不能轉為 {state}")
        self.manifest["status"] = state
        self.history.append({"state": state, "ts": now_iso(), **info})
        self.save()
        self.log("state_changed", state=state, **info)

    def require(self, *states: str, action: str, hint: str = "") -> None:
        if self.status not in states:
            raise InvalidState(
                f"{self.id} 目前狀態 {self.status}，無法{action}（需要 {' / '.join(states)}）。{hint}".rstrip()
            )

    # ---- files -----------------------------------------------------------

    def save(self) -> None:
        self.write_json("manifest.json", self.manifest)

    def log(self, event: str, **fields) -> None:
        path = self.dir / "execution_log.json"
        events = json.loads(path.read_text(encoding="utf-8"))
        events.append({"ts": now_iso(), "event": event, **fields})
        path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_json(self, name: str, obj) -> Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_json(self, name: str):
        return json.loads((self.dir / name).read_text(encoding="utf-8"))

    def write_text(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    @property
    def plan(self) -> dict:
        return self.read_json("analysis_plan.json")
