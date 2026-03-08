#!/usr/bin/env python3
"""
Trust Graph Automation

Automated exploration that connects to TN3270, logs in, navigates the system,
and populates the trust graph with real discovered relationships.
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

# Import TN3270 connection
try:
    from agent_tools import (
        connect_mainframe, disconnect_mainframe, send_terminal_key,
        read_screen, connection, TN3270_AVAILABLE
    )
except ImportError:
    TN3270_AVAILABLE = False
    connection = None

# Import trust graph
try:
    from trust_graph import get_trust_graph, TrustGraph
    from graph_tools import update_graph_from_screen, classify_panel, extract_identifiers
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False

# Import methodology engine
try:
    from methodology_engine import get_methodology_engine, ScreenAnalysis
    METHODOLOGY_AVAILABLE = True
except ImportError:
    METHODOLOGY_AVAILABLE = False


@dataclass
class ExplorationStep:
    """A single step in the automated exploration."""
    name: str
    action: str  # connect, string, enter, pf, clear, wait
    value: str = ""
    wait_seconds: float = 1.0
    expect: List[str] = field(default_factory=list)
    graph_node_type: Optional[str] = None
    graph_node_label: Optional[str] = None
    description: str = ""


@dataclass
class ExplorationResult:
    """Result of running an exploration."""
    success: bool
    steps_completed: int
    steps_total: int
    nodes_added: int
    edges_added: int
    screens_captured: List[Dict]
    errors: List[str]
    duration_seconds: float


class TrustGraphAutomation:
    """
    Automated trust graph builder.
    
    Connects to TN3270, navigates through the system, and builds the trust graph
    from real observed relationships.
    """
    
    def __init__(self, host: str = "localhost", port: int = 3270):
        self.host = host
        self.port = port
        self.screens_captured: List[Dict] = []
        self.errors: List[str] = []
        self.nodes_added = 0
        self.edges_added = 0
        self.running = False
        self.on_progress: Optional[Callable] = None
    
    def _log(self, message: str):
        """Log a message and call progress callback if set."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        if self.on_progress:
            self.on_progress(log_entry)
    
    def _capture_screen(self, step_name: str) -> Optional[str]:
        """Capture the current screen and add to trust graph."""
        if not TN3270_AVAILABLE or not connection:
            return None
        
        try:
            screen_text = read_screen()
            if not screen_text:
                return None
            
            # Store capture
            self.screens_captured.append({
                "step": step_name,
                "timestamp": datetime.now().isoformat(),
                "screen": screen_text[:500]
            })
            
            # Update trust graph from screen
            if GRAPH_AVAILABLE:
                graph = get_trust_graph()
                before_nodes = len(graph.nodes)
                before_edges = len(graph.edges)
                
                source = f"{self.host}:{self.port}"
                update_graph_from_screen(graph, screen_text, source)
                
                self.nodes_added += len(graph.nodes) - before_nodes
                self.edges_added += len(graph.edges) - before_edges
            
            # Run methodology analysis
            if METHODOLOGY_AVAILABLE:
                engine = get_methodology_engine()
                analysis = engine.analyze_screen(screen_text)
                self._log(f"  → Control Plane: {analysis.control_plane} ({int(analysis.control_plane_confidence*100)}%)")
            
            return screen_text
        except Exception as e:
            self.errors.append(f"Screen capture error: {e}")
            return None
    
    def _execute_step(self, step: ExplorationStep) -> bool:
        """Execute a single exploration step."""
        self._log(f"Step: {step.name}")
        
        try:
            if step.action == "connect":
                host_port = step.value or f"{self.host}:{self.port}"
                success, message = connect_mainframe(host_port)
                if not success:
                    self.errors.append(f"Connect failed: {message}")
                    return False
                time.sleep(step.wait_seconds)
                
            elif step.action == "string":
                send_terminal_key("string", step.value)
                time.sleep(0.3)
                
            elif step.action == "enter":
                send_terminal_key("enter")
                time.sleep(step.wait_seconds)
                
            elif step.action == "pf":
                pf_num = step.value if step.value else "3"
                send_terminal_key("pf", str(pf_num))
                time.sleep(step.wait_seconds)
                
            elif step.action == "clear":
                send_terminal_key("clear")
                time.sleep(step.wait_seconds)
                
            elif step.action == "wait":
                time.sleep(float(step.value) if step.value else step.wait_seconds)
            
            # Capture screen after action
            screen = self._capture_screen(step.name)
            
            # Check expectations
            if step.expect and screen:
                screen_upper = screen.upper()
                found = any(exp.upper() in screen_upper for exp in step.expect)
                if not found:
                    self._log(f"  ⚠ Expected one of: {step.expect}")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Step '{step.name}' failed: {e}")
            return False
    
    def get_session_stack_exploration(self) -> List[ExplorationStep]:
        """
        Standard exploration: VTAM → TSO → ISPF → Datasets → SDSF → Logoff
        
        This builds the core trust graph showing session stack relationships.
        """
        return [
            ExplorationStep(
                name="Connect to TK5",
                action="connect",
                value=f"{self.host}:{self.port}",
                wait_seconds=2.0,
                expect=["VTAM", "LOGON", "USS", "NVAS"],
                graph_node_type="EntryPoint",
                description="Establish TN3270 connection to VTAM"
            ),
            ExplorationStep(
                name="Enter TSO",
                action="string",
                value="TSO",
                wait_seconds=0.5,
                description="Request TSO application"
            ),
            ExplorationStep(
                name="Submit TSO request",
                action="enter",
                wait_seconds=2.0,
                expect=["LOGON", "TSO/E", "USERID"],
                graph_node_type="Panel",
                description="Navigate from VTAM to TSO logon"
            ),
            ExplorationStep(
                name="Enter userid",
                action="string",
                value="HERC01",
                wait_seconds=0.5,
                description="Enter TSO userid"
            ),
            ExplorationStep(
                name="Submit userid",
                action="enter",
                wait_seconds=2.0,
                expect=["PASSWORD", "ENTER PASSWORD"],
                description="Submit userid for authentication"
            ),
            ExplorationStep(
                name="Enter password",
                action="string",
                value="CUL8TR",
                wait_seconds=0.5,
                description="Enter password"
            ),
            ExplorationStep(
                name="Submit password",
                action="enter",
                wait_seconds=3.0,
                expect=["READY", "LOGON", "IKJ"],
                graph_node_type="Panel",
                description="Complete TSO authentication - identity now bound"
            ),
            ExplorationStep(
                name="Launch ISPF",
                action="string",
                value="ISPF",
                wait_seconds=0.5,
                description="Request ISPF application"
            ),
            ExplorationStep(
                name="Enter ISPF",
                action="enter",
                wait_seconds=3.0,
                expect=["ISPF", "OPTION", "PRIMARY"],
                graph_node_type="Panel",
                graph_node_label="ISPF_PRIMARY",
                description="Enter ISPF - human interaction plane"
            ),
            ExplorationStep(
                name="Navigate to RFE",
                action="string",
                value="=M",
                wait_seconds=0.5,
                description="Jump to MVS menu"
            ),
            ExplorationStep(
                name="Enter RFE",
                action="enter",
                wait_seconds=2.0,
                expect=["RFE", "OPTION", "REVIEW"],
                graph_node_type="Panel",
                graph_node_label="RFE",
                description="Enter Review Front End"
            ),
            ExplorationStep(
                name="Select option 1",
                action="string",
                value="1",
                wait_seconds=0.5,
                description="Select RFE option 1"
            ),
            ExplorationStep(
                name="Enter RFE main",
                action="enter",
                wait_seconds=2.0,
                expect=["OPTION", "UTILITIES"],
                description="RFE main menu"
            ),
            ExplorationStep(
                name="Go to Utilities",
                action="string",
                value="3",
                wait_seconds=0.5,
                description="Select Utilities"
            ),
            ExplorationStep(
                name="Enter Utilities",
                action="enter",
                wait_seconds=2.0,
                expect=["UTILITIES", "DSLIST", "DATASET"],
                graph_node_type="Panel",
                description="Utilities menu"
            ),
            ExplorationStep(
                name="Go to Dataset List",
                action="string",
                value="4",
                wait_seconds=0.5,
                description="Select Dataset List"
            ),
            ExplorationStep(
                name="Enter Dataset List",
                action="enter",
                wait_seconds=2.0,
                expect=["DSLIST", "DATA SET"],
                graph_node_type="Panel",
                graph_node_label="DSLIST",
                description="Dataset list panel"
            ),
            ExplorationStep(
                name="List SYS1 datasets",
                action="string",
                value="SYS1",
                wait_seconds=0.5,
                description="Enter SYS1 prefix"
            ),
            ExplorationStep(
                name="Submit SYS1 search",
                action="enter",
                wait_seconds=3.0,
                expect=["SYS1", "PARMLIB", "PROCLIB", "LINKLIB"],
                graph_node_type="Dataset",
                description="List system datasets - these define z/OS config"
            ),
            ExplorationStep(
                name="Return from DSLIST",
                action="pf",
                value="3",
                wait_seconds=1.5,
                description="PF3 to go back"
            ),
            ExplorationStep(
                name="Return to Utilities",
                action="pf",
                value="3",
                wait_seconds=1.5,
                description="PF3 to go back"
            ),
            ExplorationStep(
                name="Return to RFE",
                action="pf",
                value="3",
                wait_seconds=1.5,
                description="PF3 to go back"
            ),
            ExplorationStep(
                name="Go to SDSF",
                action="string",
                value="=S",
                wait_seconds=0.5,
                description="Jump to SDSF"
            ),
            ExplorationStep(
                name="Enter SDSF",
                action="enter",
                wait_seconds=2.0,
                expect=["SDSF", "DISPLAY", "PRIMARY"],
                graph_node_type="Panel",
                graph_node_label="SDSF",
                description="SDSF - JES interface, deferred execution plane"
            ),
            ExplorationStep(
                name="Display Active jobs",
                action="string",
                value="DA",
                wait_seconds=0.5,
                description="Display Active command"
            ),
            ExplorationStep(
                name="Show Active jobs",
                action="enter",
                wait_seconds=2.0,
                expect=["ACTIVE", "JOBNAME", "OWNERID"],
                graph_node_type="Job",
                description="Active address spaces - long-running processes"
            ),
            ExplorationStep(
                name="Return from DA",
                action="pf",
                value="3",
                wait_seconds=1.5,
                description="PF3 to go back"
            ),
            ExplorationStep(
                name="Exit SDSF",
                action="pf",
                value="3",
                wait_seconds=1.5,
                description="Exit SDSF"
            ),
            ExplorationStep(
                name="Exit ISPF",
                action="pf",
                value="3",
                wait_seconds=2.0,
                expect=["READY", "END"],
                description="Exit ISPF to TSO READY"
            ),
            ExplorationStep(
                name="Confirm exit",
                action="pf",
                value="3",
                wait_seconds=2.0,
                expect=["READY"],
                description="Confirm exit if prompted"
            ),
            ExplorationStep(
                name="Run LISTALC",
                action="string",
                value="LISTALC STATUS",
                wait_seconds=0.5,
                description="List allocations"
            ),
            ExplorationStep(
                name="Execute LISTALC",
                action="enter",
                wait_seconds=2.0,
                expect=["LISTALC", "KEEP", "SHR", "ALLOC"],
                graph_node_type="Dataset",
                description="Show identity context - allocated datasets"
            ),
            ExplorationStep(
                name="Logoff TSO",
                action="string",
                value="LOGOFF",
                wait_seconds=0.5,
                description="Request logoff"
            ),
            ExplorationStep(
                name="Execute Logoff",
                action="enter",
                wait_seconds=2.0,
                expect=["LOGOFF", "VTAM", "LOGGED OFF"],
                description="Return to VTAM - identity unbound"
            ),
        ]
    
    def run_exploration(self, steps: Optional[List[ExplorationStep]] = None) -> ExplorationResult:
        """
        Run the automated exploration.
        
        Returns ExplorationResult with stats.
        """
        if not TN3270_AVAILABLE:
            return ExplorationResult(
                success=False,
                steps_completed=0,
                steps_total=0,
                nodes_added=0,
                edges_added=0,
                screens_captured=[],
                errors=["TN3270 not available"],
                duration_seconds=0
            )
        
        if steps is None:
            steps = self.get_session_stack_exploration()
        
        self.running = True
        self.screens_captured = []
        self.errors = []
        self.nodes_added = 0
        self.edges_added = 0
        
        start_time = time.time()
        steps_completed = 0
        
        self._log(f"Starting exploration with {len(steps)} steps...")
        
        for i, step in enumerate(steps):
            if not self.running:
                self._log("Exploration cancelled")
                break
            
            self._log(f"[{i+1}/{len(steps)}] {step.name}")
            
            success = self._execute_step(step)
            if success:
                steps_completed += 1
            else:
                self._log(f"  ✗ Step failed, continuing...")
        
        duration = time.time() - start_time
        self.running = False
        
        self._log(f"Exploration complete: {steps_completed}/{len(steps)} steps")
        self._log(f"Graph: +{self.nodes_added} nodes, +{self.edges_added} edges")
        
        return ExplorationResult(
            success=steps_completed == len(steps),
            steps_completed=steps_completed,
            steps_total=len(steps),
            nodes_added=self.nodes_added,
            edges_added=self.edges_added,
            screens_captured=self.screens_captured,
            errors=self.errors,
            duration_seconds=duration
        )
    
    def stop(self):
        """Stop the running exploration."""
        self.running = False


# Module-level instance
_automation: Optional[TrustGraphAutomation] = None


def get_automation(host: str = "localhost", port: int = 3270) -> TrustGraphAutomation:
    """Get or create the automation instance."""
    global _automation
    if _automation is None:
        _automation = TrustGraphAutomation(host, port)
    return _automation


def run_session_stack_exploration(host: str = "localhost", port: int = 3270) -> ExplorationResult:
    """Convenience function to run the session stack exploration."""
    automation = TrustGraphAutomation(host, port)
    return automation.run_exploration()


# CLI test
if __name__ == "__main__":
    import sys
    
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3270
    
    print(f"Running trust graph automation against {host}:{port}")
    result = run_session_stack_exploration(host, port)
    
    print(f"\n{'='*50}")
    print(f"Success: {result.success}")
    print(f"Steps: {result.steps_completed}/{result.steps_total}")
    print(f"Nodes added: {result.nodes_added}")
    print(f"Edges added: {result.edges_added}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    
    if result.errors:
        print(f"\nErrors:")
        for err in result.errors:
            print(f"  - {err}")
