"""Reading research data files and inferring the data dictionary."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .errors import DataImportError

SUPPORTED_SUFFIXES = (".csv", ".xlsx")
CSV_ENCODINGS = ("utf-8-sig", "cp950")  # cp950 = Big5, common in Taiwanese Excel exports
LEVELS = ("nominal", "ordinal", "scale")


@dataclass
class Variable:
    name: str
    type: str  # numeric | string
    level: str  # nominal | ordinal | scale
    level_source: str  # inferred | user
    ambiguous: bool  # inferred level is a guess the user should confirm
    n_missing: int
    n_unique: int

    def to_dict(self) -> dict:
        return asdict(self)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_table(path: Path, sheet: str | None = None) -> pd.DataFrame:
    if not path.is_file():
        raise DataImportError(f"找不到檔案：{path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DataImportError(
            f"不支援的檔案格式：{suffix or '(無副檔名)'}。目前支援 {', '.join(SUPPORTED_SUFFIXES)}。"
        )
    if suffix == ".csv":
        text = _decode_csv(path)
        header = next(csv.reader(io.StringIO(text)), [])
        _check_header(header)
        df = pd.read_csv(io.StringIO(text))
    else:
        try:
            header_df = pd.read_excel(path, sheet_name=sheet or 0, header=None, nrows=1)
        except ValueError as e:
            raise DataImportError(f"找不到工作表：{sheet}（{e}）") from e
        _check_header(["" if pd.isna(v) else str(v) for v in header_df.iloc[0]] if len(header_df) else [])
        df = pd.read_excel(path, sheet_name=sheet or 0)
    if len(df) == 0:
        raise DataImportError(f"檔案沒有任何資料列：{path.name}")
    df.columns = [str(c) for c in df.columns]
    return df


def _decode_csv(path: Path) -> str:
    raw = path.read_bytes()
    for enc in CSV_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise DataImportError(f"無法辨識檔案編碼（已嘗試 {', '.join(CSV_ENCODINGS)}）：{path.name}")


def _check_header(header: list[str]) -> None:
    if not header:
        raise DataImportError("檔案沒有欄位名稱列。")
    names = [h.strip() for h in header]
    if any(n == "" for n in names):
        raise DataImportError("有欄位沒有名稱，請在第一列補上欄位名稱。")
    dups = sorted({n for n in names if names.count(n) > 1})
    if dups:
        raise DataImportError(f"欄位名稱重複：{', '.join(dups)}")


def write_canonical_csv(df: pd.DataFrame, path: Path) -> None:
    """UTF-8, empty cell = missing. Both engines read this file.

    Whole-number float columns (integers with gaps) are written as integers, so a
    group code reads as "1" rather than "1.0" in every engine."""
    out = df.copy()
    for name in out.columns:
        s = out[name]
        if pd.api.types.is_float_dtype(s) and s.notna().any() and bool((s.dropna() == s.dropna().round()).all()):
            out[name] = s.astype("Int64")
    out.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def read_canonical_csv(path: Path, text_columns: list[str] = ()) -> pd.DataFrame:
    header = pd.read_csv(path, encoding="utf-8", nrows=0).columns
    return pd.read_csv(path, encoding="utf-8", dtype={c: str for c in text_columns if c in header})


def infer_dictionary(df: pd.DataFrame) -> dict[str, Variable]:
    return {name: _infer_variable(name, df[name]) for name in df.columns}


def _infer_variable(name: str, s: pd.Series) -> Variable:
    values = s.dropna()
    n_unique = int(values.nunique())
    common = {"name": name, "n_missing": int(s.isna().sum()), "n_unique": n_unique, "level_source": "inferred"}
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        uniques = set(values.unique().tolist())
        is_integer = bool(len(values)) and bool((values == values.round()).all())
        if uniques and (uniques <= {0, 1} or (is_integer and n_unique == 2)):
            # dichotomous codes such as 0/1 or 1/2
            return Variable(type="numeric", level="nominal", ambiguous=True, **common)
        if is_integer and 3 <= n_unique <= 7:
            # few distinct whole numbers (Likert items, coded categories): could be ordinal or a short scale
            return Variable(type="numeric", level="ordinal", ambiguous=True, **common)
        return Variable(type="numeric", level="scale", ambiguous=False, **common)
    return Variable(type="string", level="nominal", ambiguous=False, **common)
