"""Statistical engine adapter contract.

An adapter turns an approved analysis plan into a standalone script, runs it in
a subprocess (whitelisted interpreter, no shell, with timeout), and the script
writes `raw_outputs/results.json`. The core never computes reported statistics.
"""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from ..errors import EngineFailed, EngineUnavailable

STDERR_LIMIT = 2000


class EngineAdapter(ABC):
    name: str
    script_name: str
    install_hint: str

    @abstractmethod
    def command(self) -> list[str] | None:
        """Interpreter argv prefix, or None when the engine is not installed."""

    @abstractmethod
    def render_script(self, plan: dict, default_data: str) -> str:
        """A self-contained script: `<interpreter> script [data.csv] [results.json]`."""

    def env(self) -> dict[str, str]:
        return dict(os.environ)

    def is_available(self) -> bool:
        return self.command() is not None

    def run(self, script: Path, data: Path, out: Path, cwd: Path, timeout: float) -> None:
        cmd = self.command()
        if cmd is None:
            raise EngineUnavailable(f"找不到 {self.name} 引擎。{self.install_hint}")
        try:
            proc = subprocess.run(
                [*cmd, str(script), str(data), str(out)],
                cwd=cwd, capture_output=True, text=True, timeout=timeout, env=self.env(), check=False,
            )
        except subprocess.TimeoutExpired:
            raise EngineFailed(f"{self.name} 引擎執行逾時（{timeout:g} 秒）") from None
        if proc.returncode != 0:
            raise EngineFailed(f"{self.name} 引擎執行失敗（exit {proc.returncode}）：{proc.stderr[-STDERR_LIMIT:].strip()}")
        if not out.is_file():
            raise EngineFailed(f"{self.name} 引擎沒有產生結果檔 {out.name}")
