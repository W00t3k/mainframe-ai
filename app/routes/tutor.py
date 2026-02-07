"""
Tutor API Routes

Endpoints for the Red Team Tutor guided learning system.
"""

import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_config
from app.services.ollama import get_ollama_service
from app.constants.prompts import (
    TUTOR_PERSONAS, WALKTHROUGH_PROMPTS, build_tutor_prompt,
    PATH_SYSTEM_PROMPT, PATH_SESSION_PROMPT
)
from app.constants.paths import PATH_CATALOG, FALLBACK_STEPS

router = APIRouter(tags=["tutor"])
config = get_config()

# Import optional modules
try:
    from agent_tools import connection, read_screen
except ImportError:
    connection = None
    read_screen = lambda: "[Not connected]"

try:
    from graph_tools import classify_panel, extract_identifiers
    from trust_graph import get_trust_graph
    from graph_tools import update_graph_from_screen
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False
    classify_panel = lambda x: {}


async def build_rag_context(query: str, n_results: int = 2) -> str:
    """Build RAG context for prompts."""
    try:
        from rag_engine import get_rag_engine
        engine = get_rag_engine()
        results = await engine.query_simple(query, n_results=n_results)
        if results:
            context = "\n\n[Relevant Knowledge Base Information]\n"
            for r in results:
                context += f"---\n{r['content']}\n"
            return context
    except Exception:
        pass
    return ""


def _extract_json_block(text: str) -> dict:
    """Extract JSON block from text."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return {}
    return {}


@router.post("/analyze")
async def api_tutor_analyze(request: Request):
    """Analyze current screen with tutor context."""
    data = await request.json()
    goal = data.get("goal", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")

    if not connection or not connection.connected:
        return JSONResponse({"error": "Not connected to mainframe"})

    screen_text = read_screen()
    if not screen_text or screen_text == "[Not connected]":
        return JSONResponse({"error": "Could not read screen"})

    panel_info = {}
    if GRAPH_AVAILABLE:
        panel_info = classify_panel(screen_text)
        graph = get_trust_graph()
        update_graph_from_screen(graph, screen_text, f"{connection.host}:{connection.port}")

    goal_context = {
        'session-stack': "Focus on explaining the VTAM→TSO→ISPF session layers.",
        'batch-execution': "Focus on JCL, JES, and batch execution concepts.",
        'dataset-trust': "Focus on dataset access patterns and trust implications.",
        'panel-navigation': "Focus on panel IDs, PF keys, and navigation patterns.",
        'job-tracing': "Focus on job execution chains and program loading.",
        'free-explore': "Provide general mainframe education."
    }.get(goal, "Provide general mainframe education.")

    rag_query = f"{goal_context}\n{panel_info.get('panel_type', 'Unknown')}\n{screen_text[:1200]}"
    rag_context = await build_rag_context(rag_query, n_results=2)

    section_prompt = WALKTHROUGH_PROMPTS.get(goal, "")
    section_block = f"\n\n## Section Controller\n{section_prompt}" if section_prompt else ""

    prompt = f"""{build_tutor_prompt(tutor_id)}{section_block}{rag_context}

Current learning goal: {goal_context}

Analyze this 3270 screen:
```
{screen_text}
```

Panel classification: {panel_info.get('panel_type', 'Unknown')}
Environment: {panel_info.get('environment', 'Unknown')}

Provide your analysis in the structured format. Be educational and thorough."""

    ollama = get_ollama_service()
    result = await ollama.generate(prompt, temperature=0.7, num_predict=1500)

    # Parse structured response
    sections = {}
    current_section = None
    current_content = []

    for line in result.split('\n'):
        line_upper = line.upper().strip()
        if 'CURRENT SCREEN' in line_upper:
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'current_screen'
            current_content = []
        elif 'WHAT THIS IS' in line_upper:
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'what_this_is'
            current_content = []
        elif 'WHY IT EXISTS' in line_upper:
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'why_it_exists'
            current_content = []
        elif 'RED TEAM INSIGHT' in line_upper:
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'red_team_insight'
            current_content = []
        elif 'NEXT ACTION' in line_upper:
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'next_action'
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    if not sections:
        sections = {'current_screen': result}

    sections['graph_updated'] = GRAPH_AVAILABLE
    sections['panel_type'] = panel_info.get('panel_type', 'Unknown')

    return JSONResponse(sections)


@router.post("/suggest")
async def api_tutor_suggest(request: Request):
    """Suggest next action based on goal and current screen."""
    data = await request.json()
    goal = data.get("goal", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")

    if not connection or not connection.connected:
        return JSONResponse({"suggestion": "Connect to TK5 (localhost:3270) to begin live navigation."})

    screen_text = read_screen()
    panel_info = classify_panel(screen_text) if GRAPH_AVAILABLE else {}

    rag_query = f"{goal}\n{panel_info.get('panel_type', 'Unknown')}\n{screen_text[:1200]}"
    rag_context = await build_rag_context(rag_query, n_results=2)

    section_prompt = WALKTHROUGH_PROMPTS.get(goal, "")
    section_block = f"\n\n## Section Controller\n{section_prompt}" if section_prompt else ""

    prompt = f"""{build_tutor_prompt(tutor_id)}{section_block}{rag_context}

Learning goal: {goal}
Current panel: {panel_info.get('panel_type', 'Unknown')}

Screen:
```
{screen_text[:1500]}
```

What should the learner do next to progress toward their goal? Be specific about what to type or which key to press."""

    ollama = get_ollama_service()
    suggestion = await ollama.generate(prompt, temperature=0.7, num_predict=500)

    return JSONResponse({"suggestion": suggestion})


@router.post("/ask")
async def api_tutor_ask(request: Request):
    """Answer a question from the learner."""
    data = await request.json()
    question = data.get("question", "")
    goal = data.get("goal", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")

    screen_context = ""
    screen_text = ""
    if connection and connection.connected:
        screen_text = read_screen()
        screen_context = f"\n\nCurrent screen:\n```\n{screen_text[:1000]}\n```"

    rag_query = f"{question}\n{screen_text[:1200]}" if question else screen_text[:1200]
    rag_context = await build_rag_context(rag_query, n_results=3)

    prompt = f"""{build_tutor_prompt(tutor_id)}{rag_context}

Learning goal: {goal}
{screen_context}

Learner's question: {question}

Answer in an educational, thorough manner. Relate concepts to modern security thinking where relevant."""

    ollama = get_ollama_service()
    answer = await ollama.generate(prompt, temperature=0.7, num_predict=500)

    return JSONResponse({"answer": answer})


@router.post("/event")
async def api_tutor_event(request: Request):
    """Orchestrated tutor endpoint for Ask/Analyze/Next events."""
    data = await request.json()
    event_type = data.get("event", "ask")
    question = data.get("question", "")
    module_id = data.get("module", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")
    step = data.get("step", {})

    result = {
        "messages": [],
        "steps": [],
        "canAdvance": False,
        "diagnostics": {
            "ragUsed": False,
            "k": 0,
            "llmUsed": False,
            "terminalConnected": connection is not None and connection.connected
        }
    }

    screen_text = ""
    if connection and connection.connected:
        try:
            screen_text = read_screen()
            result["diagnostics"]["terminalConnected"] = True
        except Exception as e:
            result["messages"].append({
                "role": "system",
                "content": f"Warning: Could not read terminal screen: {str(e)}"
            })

    # RAG retrieval
    rag_context = ""
    try:
        module_info = PATH_CATALOG.get(module_id, {})
        rag_query = f"{question}\n{module_info.get('description', '')}\n{screen_text[:1200]}"
        rag_context = await build_rag_context(rag_query, n_results=4)
        if rag_context:
            result["diagnostics"]["ragUsed"] = True
            result["diagnostics"]["k"] = 4
    except Exception as e:
        result["messages"].append({
            "role": "system",
            "content": f"Warning: RAG unavailable: {str(e)}"
        })

    # Inject per-section controller prompt if this module matches a walkthrough
    section_prompt = WALKTHROUGH_PROMPTS.get(module_id, "")
    section_block = f"\n\n## Section Controller\n{section_prompt}" if section_prompt else ""

    # Build prompt based on event type
    if event_type == "ask":
        prompt = f"""{build_tutor_prompt(tutor_id)}{section_block}{rag_context}

Module: {module_id}
Current screen:
```
{screen_text[:1500]}
```

User question: {question}

Answer thoroughly and educationally. If the question relates to the current screen, explain what they're seeing."""

    elif event_type == "analyze":
        prompt = f"""{build_tutor_prompt(tutor_id)}{section_block}{rag_context}

Module: {module_id}
Analyze this TN3270 screen:
```
{screen_text}
```

Provide your analysis following the structured format:
1. CURRENT SCREEN: Plain English summary
2. WHAT THIS IS: Panel/subsystem identification
3. WHY IT EXISTS: Historical/architectural rationale
4. RED TEAM INSIGHT: Trust boundary or control-plane implication
5. NEXT ACTION: What to do next"""

    elif event_type == "next":
        step_context = f"Current step: {step.get('title', '')}\nInstruction: {step.get('instruction', '')}" if step else ""
        prompt = f"""{build_tutor_prompt(tutor_id)}{section_block}{rag_context}

Module: {module_id}
{step_context}
Current screen:
```
{screen_text[:1500]}
```

What should the learner do next to progress? Be specific about keystrokes or text to type."""

    else:
        prompt = f"{build_tutor_prompt(tutor_id)}\n\n{question}"

    ollama = get_ollama_service()
    llm_response = await ollama.generate(prompt, temperature=0.7, num_predict=1200)

    result["diagnostics"]["llmUsed"] = True
    result["messages"].append({
        "role": "assistant",
        "content": llm_response
    })

    return JSONResponse(result)


@router.post("/path_explain")
async def api_tutor_path_explain(request: Request):
    """Explain a learning path."""
    data = await request.json()
    path = data.get("path", {})
    tutor_id = data.get("tutor_id", "mentor")
    question = data.get("question", "")

    meta = "\n".join([
        f"Title: {path.get('title', '')}",
        f"Objective: {path.get('objective', '')}",
        f"Level: {path.get('level', '')}",
        f"Time: {path.get('time', '')}",
        f"Domain: {path.get('domain', '')}",
        f"Intent: {path.get('intent', '')}",
        f"Summary: {path.get('summary', '')}",
        f"Defender Outcome: {path.get('defender_outcome', '')}",
    ])

    rag_context = await build_rag_context(meta, n_results=2)
    prompt = f"""{PATH_SYSTEM_PROMPT}{rag_context}
Tutor persona: {TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS['mentor'])['name']}

Path metadata:
{meta}

User question (optional): {question or "N/A"}

Respond with:
1) What this path teaches (1-2 sentences)
2) Why it matters (1-2 sentences)
3) Is this right for me? (1-2 sentences)
4) Suggested next step: Start / Preview / Ask (1 short sentence)
"""

    ollama = get_ollama_service()
    explanation = await ollama.generate(prompt, temperature=0.6, num_predict=400)

    return JSONResponse({"explanation": explanation})


@router.post("/path_start")
async def api_tutor_path_start(request: Request):
    """Start a learning path session."""
    data = await request.json()
    path = data.get("path", {})
    tutor_id = data.get("tutor_id", "mentor")
    screen = data.get("screen", "")

    path_id = path.get("id", "")

    # Return fallback steps for reliability
    steps = FALLBACK_STEPS.get(path_id, FALLBACK_STEPS["free-explore"])
    return JSONResponse({"session": {"path_id": path_id, "steps": steps}})


@router.post("/path_verify")
async def api_tutor_path_verify(request: Request):
    """Verify if the current screen matches expected state."""
    data = await request.json()
    step = data.get("step", {})
    screen = data.get("screen", "")
    expected_signatures = step.get("expected_signature", [])
    
    if isinstance(expected_signatures, str):
        expected_signatures = [expected_signatures]

    # Fast local match
    if expected_signatures and screen:
        hit = any(sig.lower() in screen.lower() for sig in expected_signatures if sig)
        if hit:
            return JSONResponse({"verified": True})

    return JSONResponse({"verified": False, "feedback": "Screen does not match expected state."})


@router.post("/path_help")
async def api_tutor_path_help(request: Request):
    """Get help for a stuck learner."""
    data = await request.json()
    step = data.get("step", {})
    screen = data.get("screen", "")
    tutor_id = data.get("tutor_id", "mentor")

    prompt = f"""You are a red-team tutor helping a learner who is stuck.
Provide 2-3 short bullets with recovery steps.

Tutor persona: {TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS['mentor'])['name']}
Step instruction: {step.get('instruction', '')}
Expected: {step.get('expected', '')}

Screen:
{screen[:1500]}
"""

    ollama = get_ollama_service()
    help_text = await ollama.generate(prompt, temperature=0.5, num_predict=250)

    return JSONResponse({"help": help_text})
