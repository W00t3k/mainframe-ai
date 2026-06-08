"""Tests for agent schema."""
import pytest
from datetime import datetime, timezone


def test_checkpoint_enum():
    from bigiron.agent.schema import Checkpoint

    assert Checkpoint.RECON_COMPLETE.value == "recon_complete"
    assert Checkpoint.INITIAL_ACCESS.value == "initial_access"
    assert Checkpoint.PRIVILEGE_ESCALATION.value == "priv_esc"


def test_tool_call_creation():
    from bigiron.agent.schema import ToolCall

    call = ToolCall(
        tool_name="search_modules",
        arguments={"query": "mainframe", "mtype": "auxiliary"}
    )

    assert call.tool_name == "search_modules"
    assert call.arguments["query"] == "mainframe"


def test_proposed_action_creation():
    from bigiron.agent.schema import ProposedAction

    action = ProposedAction(
        module_path="auxiliary/scanner/mainframe/tso_enum",
        options={"RHOSTS": "127.0.0.1"},
        reasoning="TSO enumeration to discover valid users",
        risk_level="low"
    )

    assert action.module_path == "auxiliary/scanner/mainframe/tso_enum"
    assert action.risk_level == "low"


def test_agent_turn_creation():
    from bigiron.agent.schema import AgentTurn, ToolCall, Checkpoint

    turn = AgentTurn(
        turn_number=1,
        reasoning="Starting reconnaissance phase",
        tool_calls=[
            ToolCall(tool_name="search_modules", arguments={"query": "enum"})
        ],
        checkpoint=Checkpoint.RECON_COMPLETE
    )

    assert turn.turn_number == 1
    assert len(turn.tool_calls) == 1
    assert turn.checkpoint == Checkpoint.RECON_COMPLETE


def test_agent_turn_to_node():
    from bigiron.agent.schema import AgentTurn, Checkpoint
    from bigiron.core.schema import NodeType

    turn = AgentTurn(
        turn_number=3,
        reasoning="Analyzing discovered users",
        tool_calls=[],
        checkpoint=None
    )

    node = turn.to_node()

    assert node.node_type == NodeType.AGENT_TURN
    assert node.properties["turn_number"] == 3
    assert "Analyzing" in node.properties["reasoning"]


def test_agent_state_creation():
    from bigiron.agent.schema import AgentState, Checkpoint

    state = AgentState(
        engagement_ref="ENG-2026-001",
        goal="Assess mainframe for JCL injection vulnerabilities",
        current_turn=0,
        current_checkpoint=None,
        completed_checkpoints=[]
    )

    assert state.engagement_ref == "ENG-2026-001"
    assert state.current_turn == 0
