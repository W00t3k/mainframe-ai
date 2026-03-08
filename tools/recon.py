"""
Recon API Routes

Endpoints for mainframe reconnaissance and security assessment.
"""

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ollama import get_ollama_service
from app.constants.prompts import RECON_AI_PROMPT, EXPLAIN_SCREEN_PROMPT
from app.services.rag_context import build_rag_context

router = APIRouter(tags=["recon"])

# Import recon engine
try:
    from recon_engine import (
        TSOEnumerator, CICSEnumerator, VTAMEnumerator,
        HiddenFieldDetector, ScreenAnalyzer, ApplicationMapper,
        SystemEnumerator,
        generate_report as generate_recon_report,
    )
    RECON_AVAILABLE = True
except ImportError:
    RECON_AVAILABLE = False

# Import agent_tools
try:
    from agent_tools import connection, read_screen, connect_mainframe
except ImportError:
    connection = None
    read_screen = lambda: "[Not connected]"
    connect_mainframe = None

# Active enumerator/mapper references for stop support
_active_enumerator = None
_active_mapper = None


@router.post("/enumerate")
async def api_recon_enumerate(request: Request):
    """Run TSO/CICS/VTAM enumeration."""
    global _active_enumerator

    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection or not connection.connected:
        return JSONResponse({"error": "Not connected to a mainframe"}, status_code=400)

    data = await request.json()
    module = data.get("module", "tso")
    wordlist = data.get("wordlist")
    command_sequence = data.get("command_sequence")

    try:
        if module == "tso":
            enumerator = TSOEnumerator(userids=wordlist, command_sequence=command_sequence)
        elif module == "cics":
            enumerator = CICSEnumerator(transactions=wordlist)
        elif module == "vtam":
            enumerator = VTAMEnumerator(applids=wordlist)
        else:
            return JSONResponse({"error": f"Unknown module: {module}"}, status_code=400)

        _active_enumerator = enumerator

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, enumerator.enumerate)

        _active_enumerator = None
        return JSONResponse({"results": results})

    except Exception as e:
        _active_enumerator = None
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/enumerate/system")
async def api_recon_enumerate_system(request: Request):
    """Run live system enumeration via TSO commands (APF, RACF, catalogs, etc)."""
    global _active_enumerator

    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)

    # Auto-connect if not connected
    if not connection or not connection.connected:
        if connect_mainframe:
            try:
                loop = asyncio.get_running_loop()
                success, msg = await loop.run_in_executor(
                    None, connect_mainframe, "localhost:3270"
                )
                if not success:
                    return JSONResponse(
                        {"error": f"Auto-connect failed: {msg}"},
                        status_code=400,
                    )
            except Exception as e:
                return JSONResponse(
                    {"error": f"Auto-connect failed: {e}"},
                    status_code=400,
                )
        else:
            return JSONResponse(
                {"error": "Not connected to a mainframe"},
                status_code=400,
            )

    try:
        data = await request.json()
    except Exception:
        data = {}
    userid = data.get("userid", "HERC01")
    password = data.get("password", "CUL8TR")
    commands = data.get("commands")  # None = all

    try:
        enumerator = SystemEnumerator(userid=userid, password=password, commands=commands)
        _active_enumerator = enumerator

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, enumerator.enumerate)

        _active_enumerator = None
        return JSONResponse({"results": results})

    except Exception as e:
        _active_enumerator = None
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/enumerate/stop")
async def api_recon_enumerate_stop():
    """Stop a running enumeration."""
    global _active_enumerator
    if _active_enumerator:
        _active_enumerator.stop()
        _active_enumerator = None
    return JSONResponse({"success": True})


@router.post("/hidden-fields")
async def api_recon_hidden_fields():
    """Detect hidden fields on current screen."""
    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection or not connection.connected:
        return JSONResponse({"error": "Not connected"}, status_code=400)

    try:
        detector = HiddenFieldDetector()
        loop = asyncio.get_running_loop()
        fields = await loop.run_in_executor(None, detector.detect)
        return JSONResponse({"fields": fields})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/analyze-screen")
async def api_recon_analyze_screen():
    """Analyze current screen for security patterns."""
    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection or not connection.connected:
        return JSONResponse({"error": "Not connected"}, status_code=400)

    try:
        analyzer = ScreenAnalyzer()
        loop = asyncio.get_running_loop()
        findings = await loop.run_in_executor(None, analyzer.analyze_current_screen)
        return JSONResponse({"findings": findings})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/map")
async def api_recon_map(request: Request):
    """Run application mapper from current screen."""
    global _active_mapper

    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection or not connection.connected:
        return JSONResponse({"error": "Not connected"}, status_code=400)

    data = await request.json()
    max_depth = min(int(data.get("max_depth", 3)), 5)

    try:
        mapper = ApplicationMapper(max_depth=max_depth)
        _active_mapper = mapper

        loop = asyncio.get_running_loop()
        tree = await loop.run_in_executor(None, mapper.map)

        stats = mapper.stats
        _active_mapper = None
        return JSONResponse({"tree": tree, "stats": stats})

    except Exception as e:
        _active_mapper = None
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/map/stop")
async def api_recon_map_stop():
    """Stop a running mapper."""
    global _active_mapper
    if _active_mapper:
        _active_mapper.stop()
        _active_mapper = None
    return JSONResponse({"success": True})


@router.post("/report")
async def api_recon_report(request: Request):
    """Generate assessment report."""
    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)

    data = await request.json()
    fmt = data.get("format", "json")
    enumerate_results = data.get("enumerate_results", [])
    hidden_fields_data = data.get("hidden_fields", [])
    screen_findings_data = data.get("screen_findings", [])
    map_tree_data = data.get("map_tree", [])

    try:
        report = generate_recon_report(
            enumerate_results=enumerate_results,
            hidden_fields=hidden_fields_data,
            screen_findings=screen_findings_data,
            map_tree=map_tree_data,
            fmt=fmt,
        )
        return JSONResponse({"report": report})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/ai-analyze")
async def api_recon_ai_analyze(request: Request):
    """Send recon results to Ollama for AI-assisted interpretation."""
    data = await request.json()
    sections = []

    enum_results = data.get("enumerate_results", [])
    if enum_results:
        valid = [r for r in enum_results if r.get("status") in ("valid", "auth_required", "locked", "valid_blank")]
        invalid = [r for r in enum_results if r.get("status") == "invalid"]
        sections.append(f"## Enumeration Results\n- {len(enum_results)} targets tested\n- {len(valid)} valid, {len(invalid)} invalid")
        for r in valid[:20]:
            name = r.get("userid") or r.get("transaction_id") or r.get("applid", "?")
            sections.append(f"  - **{name}**: {r['status']} ({r['message']})")

    hidden = data.get("hidden_fields", [])
    if hidden:
        sections.append(f"\n## Hidden Fields\n- {len(hidden)} hidden fields detected")
        for f in hidden[:10]:
            sections.append(f"  - Row {f['row']}, Col {f['col']}: type={f['field_type']}, content=`{f.get('content', '')[:40]}`")

    findings = data.get("screen_findings", [])
    if findings:
        sections.append(f"\n## Screen Findings\n- {len(findings)} patterns matched")
        for f in findings[:15]:
            sections.append(f"  - [{f['severity'].upper()}] {f['description']}: `{f['match']}`")

    screen_text = data.get("current_screen", "")
    if screen_text:
        sections.append(f"\n## Current Screen\n```\n{screen_text[:1500]}\n```")

    if not sections:
        return JSONResponse({"error": "No recon data provided. Run enumeration or screen analysis first."}, status_code=400)

    context = "\n".join(sections)
    prompt = RECON_AI_PROMPT + "\n\n---\n\n" + context

    ollama = get_ollama_service()
    ai_response = await ollama.generate(prompt, temperature=0.4, num_predict=2048)

    return JSONResponse({"analysis": ai_response})


@router.post("/explain-screen")
async def api_recon_explain_screen(request: Request):
    """Explain the current screen through the methodology lens."""
    if not connection or not connection.connected:
        return JSONResponse({"error": "Not connected to a mainframe"}, status_code=400)

    screen_text = read_screen()
    if not screen_text or screen_text == "[Not connected]":
        return JSONResponse({"error": "Could not read screen"}, status_code=400)

    data = await request.json()
    walkthrough_context = data.get("walkthrough_context", "")

    prompt = EXPLAIN_SCREEN_PROMPT
    if walkthrough_context:
        prompt += f"\n\nWalkthrough context: {walkthrough_context}"

    rag_context = await build_rag_context(screen_text[:800], n_results=2)
    if rag_context:
        prompt += rag_context

    prompt += f"\n\n---\n\nCurrent TN3270 Screen:\n```\n{screen_text}\n```"

    ollama = get_ollama_service()
    explanation = await ollama.generate(prompt, temperature=0.5, num_predict=1500)

    return JSONResponse({"explanation": explanation, "screen": screen_text})
