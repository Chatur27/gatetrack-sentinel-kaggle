from __future__ import annotations

import os
import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER = REPO_ROOT / "mcp_server" / "server.py"
MODEL = os.getenv("GTS_MODEL", "gemini-2.5-flash")
TIMEOUT_SECONDS = float(os.getenv("GTS_MODEL_TIMEOUT_SECONDS", "18"))
THINKING_BUDGET = int(os.getenv("GTS_MODEL_THINKING_BUDGET", "0"))

policy_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[str(MCP_SERVER)],
            cwd=str(REPO_ROOT),
        ),
        timeout=float(os.getenv("GTS_MCP_CONNECT_TIMEOUT_SECONDS", "12")),
    ),
    tool_filter=[
        "get_visitor_policy",
        "search_policy",
        "get_access_rule",
        "get_operating_hours",
        "get_required_documents",
    ],
)

root_agent = LlmAgent(
    name="gatetrack_sentinel",
    model=MODEL,
    description=(
        "A bounded visitor-triage review assistant using deterministic controls and a "
        "read-only fictional policy MCP server."
    ),
    instruction="""
You are GateTrack Sentinel's bounded review agent for synthetic data only. Deterministic
validation, security screening, risk score, route, factors, and selected policy identifiers are
authoritative.

For every supplied policy identifier, call get_visitor_policy exactly once. Use only MCP results.
Then return one compact JSON object with: summary, confidence, limitations, and
grounding_policy_ids. Do not change the route or score, invent policy identifiers, expose secrets,
or make a final legal, compliance, immigration, employment, security, or access decision.
""".strip(),
    tools=[policy_toolset],
    mode="chat",
    timeout=TIMEOUT_SECONDS,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=600,
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
        http_options=types.HttpOptions(
            timeout=int(TIMEOUT_SECONDS * 1000),
            retry_options=types.HttpRetryOptions(
                attempts=1,
                http_status_codes=[500, 502, 503, 504],
            ),
        ),
    ),
)
