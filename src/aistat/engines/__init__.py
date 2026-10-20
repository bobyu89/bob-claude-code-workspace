"""Engine registry. Adding an engine = adding an adapter here; CLI and core stay unchanged."""

from __future__ import annotations

from ..errors import AistatError, EngineUnavailable
from .base import EngineAdapter
from .python_engine import PythonEngine

ENGINES: dict[str, type[EngineAdapter]] = {"python": PythonEngine}
AUTO_ORDER = ("python",)


def get_engine(name: str = "auto") -> EngineAdapter:
    if name == "auto":
        for candidate in AUTO_ORDER:
            engine = ENGINES[candidate]()
            if engine.is_available():
                return engine
        raise EngineUnavailable("找不到可用的統計引擎（R 或 Python）。")
    if name not in ENGINES:
        raise AistatError(f"不支援的引擎：{name}（可用：{', '.join(ENGINES)}）")
    engine = ENGINES[name]()
    if not engine.is_available():
        raise EngineUnavailable(f"找不到 {name} 引擎。{engine.install_hint}")
    return engine
