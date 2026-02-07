"""
Methodology Engine API Routes

Exposes the control-plane assessment methodology via REST endpoints.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/methodology", tags=["methodology"])

try:
    from methodology_engine import (
        get_methodology_engine,
        analyze_screen,
        CONTROL_PLANES,
        BROKEN_ASSUMPTIONS,
        ASSESSMENT_QUESTIONS
    )
    METHODOLOGY_AVAILABLE = True
except ImportError:
    METHODOLOGY_AVAILABLE = False


@router.get("/status")
async def methodology_status():
    """Check if methodology engine is available."""
    return JSONResponse({
        "available": METHODOLOGY_AVAILABLE,
        "version": "1.0.0",
        "framework": {
            "control_planes": 5,
            "broken_assumptions": 5,
            "assessment_questions": 5
        }
    })


@router.get("/framework")
async def get_framework():
    """Return the complete methodology framework."""
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    return JSONResponse({
        "control_planes": CONTROL_PLANES,
        "broken_assumptions": BROKEN_ASSUMPTIONS,
        "assessment_questions": ASSESSMENT_QUESTIONS
    })


@router.get("/control-planes")
async def get_control_planes():
    """Return all control plane definitions."""
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    return JSONResponse({"control_planes": CONTROL_PLANES})


@router.get("/control-planes/{plane_name}")
async def get_control_plane(plane_name: str):
    """Get details about a specific control plane."""
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    plane = CONTROL_PLANES.get(plane_name.upper())
    if not plane:
        return JSONResponse({"error": f"Unknown control plane: {plane_name}"}, status_code=404)
    
    return JSONResponse({"name": plane_name.upper(), **plane})


@router.get("/broken-assumptions")
async def get_broken_assumptions():
    """Return all broken assumption definitions."""
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    return JSONResponse({"broken_assumptions": BROKEN_ASSUMPTIONS})


@router.get("/assessment-questions")
async def get_assessment_questions():
    """Return all assessment question definitions."""
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    return JSONResponse({"assessment_questions": ASSESSMENT_QUESTIONS})


@router.post("/analyze")
async def analyze_screen_endpoint(request: Request):
    """
    Analyze a TN3270 screen through the methodology workflow.
    
    Request body: {"screen_text": "..."}
    
    Returns the full analysis:
    - Control plane classification
    - Broken assumption identification
    - Assessment question selection
    - Evidence extraction
    - Next action recommendation
    """
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    try:
        data = await request.json()
        screen_text = data.get("screen_text", "")
        
        if not screen_text.strip():
            return JSONResponse({"error": "screen_text is required"}, status_code=400)
        
        engine = get_methodology_engine()
        analysis = engine.analyze_screen(screen_text)
        
        return JSONResponse({
            "success": True,
            "analysis": analysis.to_dict(),
            "summary": analysis.to_summary()
        })
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/analyze-current")
async def analyze_current_screen(request: Request):
    """
    Analyze the current TN3270 screen from an active terminal session.
    
    Request body: {"session_id": "..."}  (optional, uses default if not provided)
    """
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    try:
        from agent_tools import get_screen_text, TN3270_AVAILABLE
        
        if not TN3270_AVAILABLE:
            return JSONResponse({"error": "TN3270 not available"}, status_code=503)
        
        screen_text = get_screen_text()
        if not screen_text or not screen_text.strip():
            return JSONResponse({"error": "No screen content available"}, status_code=400)
        
        engine = get_methodology_engine()
        analysis = engine.analyze_screen(screen_text)
        
        return JSONResponse({
            "success": True,
            "analysis": analysis.to_dict(),
            "summary": analysis.to_summary(),
            "screen_text": screen_text
        })
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/history")
async def get_analysis_history():
    """Get recent screen analysis history."""
    if not METHODOLOGY_AVAILABLE:
        return JSONResponse({"error": "Methodology engine not available"}, status_code=503)
    
    engine = get_methodology_engine()
    history = [a.to_dict() for a in engine.analysis_history[-20:]]
    
    return JSONResponse({
        "count": len(history),
        "history": history
    })
