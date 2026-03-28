"""
Trust Graph API Routes

Endpoints for the BloodHound-inspired trust relationship graph.
"""

import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_config

router = APIRouter(tags=["graph"])
config = get_config()

# Import graph modules
try:
    from trust_graph import get_trust_graph, TrustGraph
    from graph_tools import (
        classify_panel, extract_identifiers, parse_jcl, parse_sysout,
        update_graph_from_jcl, update_graph_from_sysout, update_graph_from_screen,
        generate_finding
    )
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False
    get_trust_graph = None

# Import agent_tools for screen reading
try:
    from agent_tools import connection, read_screen
except ImportError:
    connection = None
    read_screen = lambda: "[Not connected]"


@router.get("/stats")
async def api_graph_stats():
    """Get trust graph statistics."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available", "nodes": 0, "edges": 0})
    graph = get_trust_graph()
    stats = graph.get_stats()
    return JSONResponse(stats)


@router.get("/nodes")
async def api_graph_nodes():
    """Get all nodes in the trust graph."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"nodes": []})
    graph = get_trust_graph()
    nodes = [
        {
            "id": node.id,
            "type": node.node_type,
            "label": node.label,
            "properties": node.properties,
            "first_seen": node.first_seen,
            "last_seen": node.last_seen
        }
        for node in graph.nodes.values()
    ]
    return JSONResponse({"nodes": nodes})


@router.get("/edges")
async def api_graph_edges():
    """Get all edges in the trust graph."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"edges": []})
    graph = get_trust_graph()
    edges = [
        {
            "id": edge.id,
            "type": edge.edge_type,
            "source": edge.source_id,
            "target": edge.target_id,
            "properties": edge.properties,
            "confidence": edge.confidence
        }
        for edge in graph.edges.values()
    ]
    return JSONResponse({"edges": edges})


@router.get("/query/{query_name}")
async def api_graph_query(query_name: str, request: Request):
    """Run a named query against the trust graph."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available", "results": []})

    graph = get_trust_graph()
    params = dict(request.query_params)

    try:
        results = graph.query(query_name, **params)
        return JSONResponse({
            "query": query_name,
            "results": results,
            "count": len(results)
        })
    except ValueError as e:
        return JSONResponse({"error": str(e), "results": []}, status_code=400)


@router.post("/ingest-jcl")
async def api_graph_ingest_jcl(request: Request):
    """Ingest JCL text into the trust graph."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    data = await request.json()
    jcl_text = data.get("jcl", "")
    source = data.get("source", "manual_upload")

    if not jcl_text:
        return JSONResponse({"error": "No JCL provided"}, status_code=400)

    jcl_parsed = parse_jcl(jcl_text)
    graph = get_trust_graph()
    result = update_graph_from_jcl(graph, jcl_parsed, {"type": "jcl", "source": source})

    return JSONResponse(result)


@router.post("/ingest-sysout")
async def api_graph_ingest_sysout(request: Request):
    """Ingest SYSOUT text into the trust graph."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    data = await request.json()
    sysout_text = data.get("sysout", "")
    source = data.get("source", "manual_upload")

    if not sysout_text:
        return JSONResponse({"error": "No SYSOUT provided"}, status_code=400)

    sysout_parsed = parse_sysout(sysout_text)
    graph = get_trust_graph()
    result = update_graph_from_sysout(graph, sysout_parsed, {"type": "sysout", "source": source})

    return JSONResponse(result)


@router.post("/ingest-screen")
async def api_graph_ingest_screen(request: Request):
    """Ingest current screen into the trust graph."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    if not connection or not connection.connected:
        return JSONResponse({"error": "Not connected to mainframe"}, status_code=400)

    screen_text = read_screen()
    graph = get_trust_graph()
    result = update_graph_from_screen(graph, screen_text, f"{connection.host}:{connection.port}")

    return JSONResponse(result)


@router.get("/export/json")
async def api_graph_export_json():
    """Export trust graph as JSON."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    return JSONResponse(graph.export_json())


@router.get("/export/dot")
async def api_graph_export_dot():
    """Export trust graph as Graphviz DOT format."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    dot_content = graph.export_dot()
    return JSONResponse({"dot": dot_content})


@router.get("/export/d3")
async def api_graph_export_d3():
    """Export trust graph in D3.js-compatible format."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    return JSONResponse(graph.export_d3_json())


@router.post("/finding")
async def api_graph_generate_finding(request: Request):
    """Generate a defensive finding from graph analysis."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    data = await request.json()

    finding = generate_finding(
        title=data.get("title", "Untitled Finding"),
        evidence=data.get("evidence", []),
        reasoning=data.get("reasoning", ""),
        confidence=data.get("confidence", "MEDIUM"),
        graph_context=data.get("graph_context", {})
    )

    return JSONResponse(finding)


@router.delete("/clear")
async def api_graph_clear():
    """Clear the trust graph (for testing)."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    graph.nodes.clear()
    graph.edges.clear()
    graph.save()

    return JSONResponse({"success": True, "message": "Graph cleared"})


@router.post("/load-demo")
async def api_graph_load_demo():
    """Load demo data into the trust graph."""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    graph = get_trust_graph()
    
    # Add demo nodes - simulating a mainframe environment
    # Entry points
    graph.add_node("EntryPoint", "VTAM01", {"applid": "TSO"})
    graph.add_node("EntryPoint", "CICSPROD", {"applid": "CICS"})
    
    # Panels
    graph.add_node("Panel", "ISPF_PRIMARY", {"panel_type": "ISPF_MAIN", "title": "ISPF Primary Option Menu"})
    graph.add_node("Panel", "ISPF_EDIT", {"panel_type": "ISPF_EDIT", "title": "Edit Entry Panel"})
    graph.add_node("Panel", "ISPF_SUBMIT", {"panel_type": "ISPF_SUBMIT", "title": "Submit Job"})
    graph.add_node("Panel", "SDSF", {"panel_type": "SDSF", "title": "SDSF Primary Option Menu"})
    
    # Jobs
    graph.add_node("Job", "PAYROLL1", {"class": "A", "owner": "PROD"})
    graph.add_node("Job", "BACKUP01", {"class": "B", "owner": "OPER"})
    graph.add_node("Job", "DEMOJOB", {"class": "A", "owner": "HERC01"})
    
    # Programs
    graph.add_node("Program", "IEBGENER", {"type": "utility"})
    graph.add_node("Program", "IEFBR14", {"type": "utility"})
    graph.add_node("Program", "PAYROLL", {"type": "application"})
    
    # Datasets
    graph.add_node("Dataset", "PROD.DATA.FILE", {"dsorg": "PS"})
    graph.add_node("Dataset", "SYS1.LINKLIB", {"dsorg": "PO"})
    graph.add_node("Dataset", "PAYROLL.MASTER", {"dsorg": "VS"})
    
    # Loadlibs
    graph.add_node("Loadlib", "SYS1.LINKLIB", {})
    graph.add_node("Loadlib", "PROD.LOADLIB", {})
    
    # CICS
    graph.add_node("CICSRegion", "CICSPROD", {"sysid": "PROD"})
    graph.add_node("Transaction", "CEMT", {"type": "admin"})
    graph.add_node("Transaction", "CEDA", {"type": "admin"})
    graph.add_node("Transaction", "PAY1", {"type": "application"})
    
    # Add edges - relationships
    vtam_id = graph.make_node_id("EntryPoint", "VTAM01")
    ispf_id = graph.make_node_id("Panel", "ISPF_PRIMARY")
    edit_id = graph.make_node_id("Panel", "ISPF_EDIT")
    submit_id = graph.make_node_id("Panel", "ISPF_SUBMIT")
    sdsf_id = graph.make_node_id("Panel", "SDSF")
    
    graph.add_edge("TRANSITIONS_TO", vtam_id, ispf_id)
    graph.add_edge("NAVIGATES_TO", ispf_id, edit_id, {"pf_key": "2"})
    graph.add_edge("NAVIGATES_TO", ispf_id, submit_id, {"command": "SUBMIT"})
    graph.add_edge("NAVIGATES_TO", ispf_id, sdsf_id, {"command": "=S"})
    
    # Job executions
    payroll_job_id = graph.make_node_id("Job", "PAYROLL1")
    payroll_pgm_id = graph.make_node_id("Program", "PAYROLL")
    payroll_ds_id = graph.make_node_id("Dataset", "PAYROLL.MASTER")
    linklib_id = graph.make_node_id("Loadlib", "SYS1.LINKLIB")
    
    graph.add_edge("SUBMITS_JOB", submit_id, payroll_job_id)
    graph.add_edge("EXECUTES", payroll_job_id, payroll_pgm_id)
    graph.add_edge("READS", payroll_job_id, payroll_ds_id)
    graph.add_edge("LOADS_FROM", payroll_pgm_id, linklib_id)
    
    demo_job_id = graph.make_node_id("Job", "DEMOJOB")
    iebgener_id = graph.make_node_id("Program", "IEBGENER")
    prod_ds_id = graph.make_node_id("Dataset", "PROD.DATA.FILE")
    
    graph.add_edge("EXECUTES", demo_job_id, iebgener_id)
    graph.add_edge("READS", demo_job_id, prod_ds_id)
    graph.add_edge("LOADS_FROM", iebgener_id, linklib_id)
    
    # CICS relationships
    cics_entry_id = graph.make_node_id("EntryPoint", "CICSPROD")
    cics_region_id = graph.make_node_id("CICSRegion", "CICSPROD")
    cemt_id = graph.make_node_id("Transaction", "CEMT")
    ceda_id = graph.make_node_id("Transaction", "CEDA")
    pay1_id = graph.make_node_id("Transaction", "PAY1")
    
    graph.add_edge("TRANSITIONS_TO", cics_entry_id, cics_region_id)
    graph.add_edge("RUNS_IN", cemt_id, cics_region_id)
    graph.add_edge("RUNS_IN", ceda_id, cics_region_id)
    graph.add_edge("RUNS_IN", pay1_id, cics_region_id)
    graph.add_edge("INVOKES", pay1_id, payroll_pgm_id)
    
    graph.save()
    
    return JSONResponse({
        "success": True,
        "message": "Demo data loaded",
        "stats": graph.get_stats()
    })


# Import automation
try:
    from graph_automation import TrustGraphAutomation, run_session_stack_exploration
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False


@router.post("/auto-explore")
async def api_graph_auto_explore(request: Request):
    """
    Run automated exploration to build the trust graph.
    
    Connects to TN3270, logs in, navigates through ISPF/SDSF,
    and populates the graph with real discovered relationships.
    """
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    
    if not AUTOMATION_AVAILABLE:
        return JSONResponse({"error": "Graph automation not available"}, status_code=400)
    
    try:
        data = await request.json()
    except:
        data = {}
    
    host = data.get("host", "localhost")
    port = data.get("port", 3270)
    
    try:
        result = run_session_stack_exploration(host, port)
        
        return JSONResponse({
            "success": result.success,
            "steps_completed": result.steps_completed,
            "steps_total": result.steps_total,
            "nodes_added": result.nodes_added,
            "edges_added": result.edges_added,
            "duration_seconds": round(result.duration_seconds, 1),
            "errors": result.errors[:5],
            "screens_captured": len(result.screens_captured)
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
