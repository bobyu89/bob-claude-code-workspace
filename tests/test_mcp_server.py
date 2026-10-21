"""MCP server: same core service, no approval tool."""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from aistat.mcp_server import create_server  # noqa: E402
from conftest import make_workspace

PAIRED = {"before": "drug1", "after": "drug2"}
EXPECTED_TOOLS = {
    "list_methods", "list_datasets", "inspect_dataset", "get_data_dictionary", "create_analysis_plan",
    "validate_analysis_plan", "execute_statistical_analysis", "retrieve_analysis_results",
    "review_statistical_results", "generate_statistical_report", "export_analysis_bundle",
}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "sleep_wide.csv")


def call(server, name, **args):
    """Call a tool through the real MCP protocol (in-process client)."""
    from mcp import Client

    async def go():
        async with Client(server) as client:
            return await client.call_tool(name, args)

    result = asyncio.run(go())
    text = result.content[0].text
    return result.is_error, (text if result.is_error else json.loads(text))


def test_tool_list_matches_spec_and_has_no_approval(ws):
    from mcp import Client

    async def go():
        async with Client(create_server(ws.root)) as client:
            return (await client.list_tools()).tools

    names = {t.name for t in asyncio.run(go())}

    assert names == EXPECTED_TOOLS
    assert not any("approve" in n for n in names)


def test_inspect_does_not_send_rows_unless_asked(ws):
    server = create_server(ws.root)

    _, default = call(server, "inspect_dataset", dataset_id="sleep_wide")
    _, preview = call(server, "inspect_dataset", dataset_id="sleep_wide", include_preview=True)

    assert "preview" not in default and default["dictionary"][1]["name"] == "drug1"
    assert len(preview["preview"]) == 5


def test_agent_cannot_execute_until_user_approves(ws):
    server = create_server(ws.root)
    _, plan = call(server, "create_analysis_plan", method="paired-t-test", variables=PAIRED)
    run_id = plan["run_id"]

    is_error, message = call(server, "execute_statistical_analysis", run_id=run_id, engine="python")
    assert is_error and "aistat approve" in message
    assert "aistat approve" in plan["next_step"]

    ws.approve(run_id, confirm=["pairing_structure"])  # the human, outside MCP
    _, executed = call(server, "execute_statistical_analysis", run_id=run_id, engine="python")
    _, results = call(server, "retrieve_analysis_results", run_id=run_id)
    _, review = call(server, "review_statistical_results", run_id=run_id)
    _, report = call(server, "generate_statistical_report", run_id=run_id, mode="learning")
    _, bundle = call(server, "export_analysis_bundle", run_id=run_id)

    assert executed["status"] == "EXECUTED"
    assert results["statistics"]["t"] == pytest.approx(4.0621, abs=1e-4)
    assert review["passed"] is True
    assert "t(9) = 4.06" in report["report"]
    assert bundle["path"].endswith(".zip") and bundle["data_included"] is False


def test_agent_edited_draft_is_still_reviewed(ws):
    server = create_server(ws.root)
    _, plan = call(server, "create_analysis_plan", method="paired-t-test", variables=PAIRED)
    ws.approve(plan["run_id"], confirm=["pairing_structure"])
    call(server, "execute_statistical_analysis", run_id=plan["run_id"], engine="python")

    is_error, message = call(server, "generate_statistical_report", run_id=plan["run_id"],
                             draft="t(9) = 7.77, p = .001。這證明藥物有效。")

    assert is_error and "values_traceable" in message and "causal_language" in message


def test_agent_can_draft_an_alternative_plan(ws):
    server = create_server(ws.root)
    _, plan = call(server, "create_analysis_plan", method="paired-t-test", variables=PAIRED)

    _, alt = call(server, "create_analysis_plan", alternative_of=plan["run_id"])

    assert alt["run_id"] != plan["run_id"]
    assert alt["method"] == "wilcoxon-signed-rank"
    assert "aistat approve" in alt["next_step"]


def test_alternative_of_cannot_be_combined_with_method(ws):
    server = create_server(ws.root)
    _, plan = call(server, "create_analysis_plan", method="paired-t-test", variables=PAIRED)

    is_error, message = call(server, "create_analysis_plan", alternative_of=plan["run_id"], method="paired-t-test")

    assert is_error and "alternative_of" in message
