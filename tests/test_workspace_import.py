import os
import stat

import pandas as pd
import pytest

from aistat.errors import AistatError
from aistat.workspace import Workspace


def write_csv(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_import_csv_registers_dataset_with_hash_and_dictionary(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    src = write_csv(tmp_path / "scores.csv", "id,group,pre,post\n1,A,10,12\n2,B,11,15\n3,A,,14\n")

    ds = ws.import_dataset(src)

    assert ds.id == "scores"
    assert ds.n_rows == 3
    assert ds.columns == ["id", "group", "pre", "post"]
    assert len(ds.sha256) == 64
    assert [d.id for d in ws.list_datasets()] == ["scores"]
    pre = ws.get_dictionary("scores")["pre"]
    assert pre.type == "numeric"
    assert pre.n_missing == 1
    assert ws.get_dictionary("scores")["group"].level == "nominal"


def test_imported_files_are_read_only(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    ds = ws.import_dataset(write_csv(tmp_path / "a.csv", "x\n1\n2\n"))

    for f in (ws.dataset_dir(ds.id) / "original.csv", ws.dataset_dir(ds.id) / "data.csv"):
        assert not os.stat(f).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)


def test_reimporting_identical_file_returns_existing_dataset(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    first = ws.import_dataset(write_csv(tmp_path / "a.csv", "x\n1\n2\n"))
    copy = write_csv(tmp_path / "copy_of_a.csv", "x\n1\n2\n")

    again = ws.import_dataset(copy)

    assert again.id == first.id
    assert len(ws.list_datasets()) == 1


def test_different_file_with_same_name_gets_new_id(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    ws.import_dataset(write_csv(tmp_path / "a.csv", "x\n1\n2\n"))
    (tmp_path / "other").mkdir()

    ds = ws.import_dataset(write_csv(tmp_path / "other" / "a.csv", "x\n3\n4\n"))

    assert ds.id == "a_2"


def test_import_excel_sheet(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    path = tmp_path / "survey.xlsx"
    with pd.ExcelWriter(path) as xw:
        pd.DataFrame({"a": [1]}).to_excel(xw, sheet_name="intro", index=False)
        pd.DataFrame({"score": [3.5, 4.0, 2.5], "sex": ["F", "M", "F"]}).to_excel(xw, sheet_name="data", index=False)

    ds = ws.import_dataset(path, sheet="data")

    assert ds.columns == ["score", "sex"]
    assert ds.n_rows == 3
    assert ds.sheet == "data"


def test_import_big5_encoded_csv(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    path = tmp_path / "big5.csv"
    path.write_bytes("性別,分數\n女,3\n男,4\n".encode("cp950"))

    ds = ws.import_dataset(path)

    assert ds.columns == ["性別", "分數"]


@pytest.mark.parametrize(
    "name,content,message",
    [
        ("missing.csv", None, "找不到檔案"),
        ("data.sav", "x", "不支援的檔案格式"),
        ("empty.csv", "x,y\n", "沒有任何資料列"),
        ("dup.csv", "x,x\n1,2\n", "欄位名稱重複"),
    ],
)
def test_import_rejects_bad_input_with_clear_message(tmp_path, name, content, message):
    ws = Workspace.init(tmp_path / "proj")
    path = tmp_path / name
    if content is not None:
        path.write_text(content, encoding="utf-8")

    with pytest.raises(AistatError, match=message):
        ws.import_dataset(path)


def test_init_is_idempotent_and_open_finds_workspace_from_subdir(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    ws.import_dataset(write_csv(tmp_path / "a.csv", "x\n1\n2\n"))

    Workspace.init(tmp_path / "proj")
    sub = tmp_path / "proj" / "notes"
    sub.mkdir()

    assert [d.id for d in Workspace.open(sub).list_datasets()] == ["a"]


def test_open_outside_workspace_fails(tmp_path):
    with pytest.raises(AistatError, match="aistat init"):
        Workspace.open(tmp_path)
