"""
Chat Service

Handles chat processing, conversation management, and RAG integration.
"""

import re
from difflib import get_close_matches
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import get_config
from app.services.seed_index.lookup import SeedIndexLookup
from app.services.seed_index.tracker import QueryMissTracker
from app.services.mainframe_memory import (
    find_mainframe_memory_entries,
    get_known_mainframe_terms,
    retrieve_mainframe_memory,
)
from app.services.mainframe_seed import (
    find_seed_definition_entries,
    format_seed_definition,
    get_seed_definition_by_title,
)
from app.services.mainframe_timeline import answer_timeline_question
from app.services.ollama import get_ollama_service
from app.services.llm_provider import get_llm_service
from app.constants.prompts import SYSTEM_PROMPT


class ChatService:
    """Service for chat processing and conversation management."""
    
    def __init__(self):
        self.config = get_config()
        self.ollama = get_ollama_service()
        self.llm = get_llm_service()
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 10
        
        # Import optional modules
        self._rag_engine = None
        self._agent_tools = None
        self._connection = None
        self._load_optional_modules()

        # Load fuzzy seed index
        self._seed_index: Optional[SeedIndexLookup] = None
        self._miss_tracker: Optional[QueryMissTracker] = None
        self._load_seed_index()
    
    def _load_optional_modules(self):
        """Load optional modules if available."""
        try:
            from rag_engine import get_rag_engine
            self._rag_engine = get_rag_engine
        except ImportError:
            pass
        
        try:
            from agent_tools import (
                connection, TOOL_DEFINITIONS, execute_tool_async,
                connect_mainframe, disconnect_mainframe, read_screen
            )
            self._connection = connection
            self._tool_definitions = TOOL_DEFINITIONS
            self._execute_tool_async = execute_tool_async
            self._connect_mainframe = connect_mainframe
            self._disconnect_mainframe = disconnect_mainframe
            self._read_screen = read_screen
        except ImportError:
            self._connection = None

    def _load_seed_index(self):
        """Load the fuzzy seed index if available."""
        index_path = Path(self.config.BASE_DIR) / "data" / "reference" / "seed_index_fuzzy.json"
        if index_path.exists():
            try:
                self._seed_index = SeedIndexLookup.from_file(index_path)
            except Exception as e:
                print(f"Failed to load fuzzy index: {e}")
                self._seed_index = None

        miss_log_path = Path(self.config.BASE_DIR) / "data" / "reference" / "query_misses.jsonl"
        self._miss_tracker = QueryMissTracker(miss_log_path)

    def _lookup_fuzzy_seed(self, query: str) -> Optional[dict]:
        """Look up query in fuzzy seed index."""
        if not self._seed_index:
            return None

        result = self._seed_index.lookup_with_suggestions(query)

        if result.get("match") and result.get("confidence", 0) >= 0.7:
            return result
        return None

    @property
    def is_connected(self) -> bool:
        """Check if connected to mainframe."""
        return self._connection is not None and self._connection.connected
    
    @property
    def connection_host(self) -> str:
        """Get the current connection host."""
        if self._connection and self._connection.connected:
            return f"{self._connection.host}:{self._connection.port}"
        return ""
    
    @property
    def current_screen(self) -> Optional[str]:
        """Get the current screen content."""
        if self._connection and self._connection.connected:
            return self._connection.current_screen
        return None
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    async def get_rag_context(self, query: str, n_results: int = 2) -> str:
        """Query RAG for relevant context."""
        context, _ = await self.get_rag_context_with_meta(query, n_results)
        return context

    async def get_rag_context_with_meta(self, query: str, n_results: int = 2) -> tuple[str, int]:
        """Query RAG and return formatted context plus result count."""
        results = await self.get_rag_results(query, n_results)
        if not results:
            return "", 0

        context = "\n\n[Relevant Knowledge Base Information]\n"
        for r in results:
            context += f"---\n{r['content']}\n"
        return context, len(results)

    async def get_rag_results(self, query: str, n_results: int = 2) -> list[dict[str, Any]]:
        """Query RAG and return raw result dictionaries."""
        if self._rag_engine is None:
            return []
        
        try:
            engine = self._rag_engine()
            return await engine.query_simple(query, n_results=n_results)
        except Exception as e:
            print(f"RAG query error: {e}")
        
        return []

    def _should_include_screen_context(self, user_message: str) -> bool:
        """Only attach live 3270 screen state when the user asks for it."""
        message = user_message.lower()
        screen_terms = (
            "screen", "terminal", "3270", "panel", "logon", "cursor",
            "session", "what do i do", "next step", "current", "connected",
            "this page", "this menu", "where am i",
        )
        return any(term in message for term in screen_terms)

    def _is_fast_mainframe_qa(self, user_message: str) -> bool:
        """Route short concept questions through a small, history-free prompt."""
        message = user_message.strip().lower()
        if len(message) > 220 or self._should_include_screen_context(user_message):
            return False

        question_starts = (
            "what is", "what's", "whats", "explain", "define", "why is",
            "what are", "why does", "how does", "how do", "what does",
            "tell me about",
        )
        concept_terms = (
            "abend", "soc", "s0c", "jcl", "jes", "racf", "tso", "ispf",
            "cics", "vtam", "apf", "dataset", "proclib", "parmlib",
            "sysout", "smf", "system/360", "system 360", "s/360", "s 360",
            "system/370", "system 370", "s/370", "s 370",
            "system/390", "system 390", "s/390", "s 390",
            "mvs", "mvs/esa", "os/390", "os 390", "z/os", "z os", "zos",
            "mainframe", "started task", "spool", "rag", "memory",
            "knowledge base",
        )
        history_terms = (
            "when", "date", "release", "released", "announce", "announced",
            "introduced", "come out", "came out", "coming out",
        )
        return (
            message.startswith(question_starts)
            or any(term in message for term in concept_terms)
            or (
                any(term in message for term in history_terms)
                and any(term in message for term in concept_terms)
            )
        )

    def _is_definition_question(self, user_message: str) -> bool:
        """Return true when the user is asking for a definition, not history."""
        message = user_message.strip().lower()
        definition_starts = (
            "what is", "what's", "whats", "what are", "define", "explain",
            "what does", "tell me about",
        )
        return message.startswith(definition_starts)

    def _is_bare_concept_query(self, user_message: str) -> bool:
        """Return true for short queries that are just a known concept name."""
        message = user_message.strip()
        if not message or len(message) > 48:
            return False
        if re.search(r"[?!,;:]", message):
            return False
        return bool(find_seed_definition_entries(message, limit=1) or find_mainframe_memory_entries(message, limit=1))

    def _extract_definition_target(self, user_message: str) -> Optional[str]:
        """Extract the concept being defined from a short definition question."""
        match = re.match(
            r"^\s*(?:what\s+is|what\s+are|what'?s|whats|define|explain|what\s+does|tell\s+me\s+about)\s+"
            r"(?:an?\s+|the\s+)?(.+?)\??\s*$",
            user_message.strip(),
            re.IGNORECASE,
        )
        if not match:
            return None
        target = re.sub(r"\s+", " ", match.group(1).strip(" .?"))
        if not target or len(target) > 80:
            return None
        return target

    def _answer_history_direct(self, user_message: str) -> Optional[str]:
        """Answer common mainframe release-date questions from RAG seed data."""
        return answer_timeline_question(user_message)

    def _normalized_abend_code(self, user_message: str) -> Optional[str]:
        """Extract Sxxx ABEND code from a query, normalizing common SOC/S0C spelling."""
        message = user_message.upper().replace("SOC", "S0C")
        message = re.sub(r"\bSC0([0-9A-F])\b", r"S0C\1", message)
        message = re.sub(r"\bSC([0-9A-F])\b", r"S0C\1", message)
        match = re.search(r"\b(S[0-9A-F][0-9A-F][0-9A-F])\b", message)
        return match.group(1) if match else None

    def _format_abend_summary(self, title: str, summary: str) -> str:
        """Format a glossary ABEND entry without asking the model to guess."""
        return (
            f"**{title}**\n"
            f"- Meaning: {summary}\n"
            "- Check: JES job log, SYSOUT, SYSUDUMP/SYSABEND, PSW or instruction offset, registers, compile listing or map, and the input record.\n"
            "- Fix direction: identify the failing instruction and correct the data, field size, addressability, or linkage issue shown by the evidence."
        )

    def _answer_abend_direct(self, user_message: str, rag_results: list[dict[str, Any]]) -> Optional[str]:
        """Return a direct RAG-derived answer for exact ABEND section matches."""
        code = self._normalized_abend_code(user_message)
        if not code:
            return None

        section = None
        title = code
        pattern = re.compile(
            rf"###\s+{re.escape(code)}\s*-\s*(.*?)(?=\s+###\s+S[0-9A-F][0-9A-F][0-9A-F]\b|\s+##\s+|\Z)",
            re.IGNORECASE | re.DOTALL,
        )

        for result in rag_results:
            content = result.get("content", "")
            match = pattern.search(content)
            if match:
                section = match.group(1).strip()
                heading_name = section.split("Cause:", 1)[0].strip(" -")
                if heading_name:
                    title = f"{code} — {heading_name}"
                break

        if not section:
            entries = find_mainframe_memory_entries(code, limit=1)
            if entries and entries[0].get("id", "").startswith("abend-"):
                return self._format_abend_summary(entries[0].get("title", code), entries[0].get("summary", ""))
            return None

        cause_match = re.search(
            r"Cause:\s*(.*?)(?=\s+Common causes:|\s+Fix:|\s+###|\Z)",
            section,
            re.IGNORECASE | re.DOTALL,
        )
        causes_match = re.search(
            r"Common causes:\s*(.*?)(?=\s+Fix:|\s+###|\Z)",
            section,
            re.IGNORECASE | re.DOTALL,
        )
        fix_match = re.search(
            r"Fix:\s*(.*?)(?=\s+###|\s+##|\Z)",
            section,
            re.IGNORECASE | re.DOTALL,
        )

        cause = " ".join(cause_match.group(1).split()) if cause_match else "See the matching RAG section."
        fixes = " ".join(fix_match.group(1).split()) if fix_match else "Review the failing step and related job output."
        if "INITIALIZE verb" in fixes:
            fixes = (
                "initialize numeric fields in a way that matches the COBOL level, "
                "check MOVE statements, and verify record layouts match the input data"
            )

        likely_causes = []
        if causes_match:
            likely_causes = [
                " ".join(item.split())
                for item in re.findall(r"-\s+(.*?)(?=\s+-\s+|\s+Fix:|\s+###|\Z)", causes_match.group(1), re.DOTALL)
                if item.strip()
            ][:3]

        likely = "; ".join(likely_causes) if likely_causes else cause
        return (
            f"**ABEND {title}**\n"
            f"- Meaning: {cause}\n"
            f"- Likely causes: {likely}\n"
            f"- Check: JES job log, SYSOUT, SYSUDUMP/SYSABEND, PSW or instruction offset, compile listing or map, and the input record.\n"
            f"- Fix direction: {fixes}"
        )

    def _extract_rag_section(self, title: str, rag_results: list[dict[str, Any]]) -> Optional[str]:
        """Extract a markdown section by title from RAG results."""
        title_pattern = re.escape(title).replace(r"\ ", r"\s+")
        pattern = re.compile(
            rf"###\s+{title_pattern}\s*(.*?)(?=\s+###\s+|\s+##\s+|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        for result in rag_results:
            match = pattern.search(result.get("content", ""))
            if match:
                return match.group(1).strip()
        return None

    def _field_from_section(self, label: str, section: str) -> str:
        """Extract a labeled field from a direct-answer RAG section."""
        labels = (
            "Definition",
            "Security impact",
            "Assessment angle",
            "Lab-safe example",
            "Aliases",
            "Question intent",
            "Answer",
        )
        stop_labels = [candidate for candidate in labels if candidate.lower() != label.lower()]
        stop_pattern = "|".join(re.escape(candidate) for candidate in stop_labels)
        match = re.search(
            rf"(?is)(?:^|\s){re.escape(label)}:\s*(.*?)(?=(?:^|\s)(?:{stop_pattern}):|\Z)",
            section,
        )
        return " ".join(match.group(1).split()) if match else ""

    def _format_memory_concept(self, entry: dict[str, Any]) -> str:
        """Format a local glossary entry in BigIron.ai answer style."""
        parts = [
            f"**{entry.get('title', 'Mainframe concept')}**",
            f"- Concept: {entry.get('summary', '')}",
        ]
        if entry.get("security_impact"):
            parts.append(f"- Security impact: {entry['security_impact']}")
        if entry.get("assessment_angle"):
            parts.append(f"- Assessment angle: {entry['assessment_angle']}")
        if entry.get("lab_safe_example"):
            parts.append(f"- Lab-safe example: {entry['lab_safe_example']}")
        return "\n".join(parts)

    def _answer_concept_direct(self, user_message: str) -> tuple[Optional[str], str]:
        """Return a fast direct answer for common mainframe concept questions."""
        if not self._is_definition_question(user_message) and not self._is_bare_concept_query(user_message):
            return None, "none"

        answers = []
        seen_titles: set[str] = set()
        used_seed = False

        for seed_entry in find_seed_definition_entries(user_message, limit=6):
            title = seed_entry.get("title", "")
            title_key = title.lower()
            if title_key in seen_titles:
                continue
            answers.append(format_seed_definition(seed_entry))
            seen_titles.add(title_key)
            used_seed = True

        entries = find_mainframe_memory_entries(user_message, limit=6)

        for entry in entries:
            title = entry.get("title", "Mainframe concept")
            title_key = title.lower()
            if title_key in seen_titles:
                continue

            if entry.get("id", "").startswith("abend-"):
                answers.append(self._format_abend_summary(title, entry.get("summary", "")))
                seen_titles.add(title_key)
                continue

            candidate_titles = [title]
            if title == "Datasets":
                candidate_titles.append("Dataset")
            if title == "Started Task Identity":
                candidate_titles.append("Started Task")

            seed_entry = None
            for candidate in candidate_titles:
                seed_entry = get_seed_definition_by_title(candidate)
                if seed_entry:
                    break

            if seed_entry:
                answers.append(format_seed_definition(seed_entry, display_title=title))
                used_seed = True
            else:
                answers.append(self._format_memory_concept(entry))
            seen_titles.add(title_key)

        if answers:
            return "\n\n".join(answers), "rag_seed_direct" if used_seed else "memory_direct"

        return None, "none"

    def _answer_rag_definition_direct(
        self,
        user_message: str,
        rag_results: list[dict[str, Any]],
    ) -> Optional[str]:
        """Extract a matching structured definition section from RAG results."""
        target = self._extract_definition_target(user_message)
        if not target:
            return None

        section = self._extract_rag_section(target, rag_results)
        if not section:
            return None

        definition = self._field_from_section("Definition", section)
        impact = self._field_from_section("Security impact", section)
        assessment = self._field_from_section("Assessment angle", section)
        example = self._field_from_section("Lab-safe example", section)

        if not any((definition, impact, assessment, example)):
            return None

        parts = [f"**{target}**"]
        if definition:
            parts.append(f"- Concept: {definition}")
        if impact:
            parts.append(f"- Security impact: {impact}")
        if assessment:
            parts.append(f"- Assessment angle: {assessment}")
        if example:
            parts.append(f"- Lab-safe example: {example}")
        return "\n".join(parts)

    def _unknown_short_concept_answer(self, user_message: str) -> Optional[str]:
        """Fail safely for unknown short concepts instead of letting the model guess."""
        match = re.match(
            r"^\s*(?:what\s+is|what'?s|whats|define|explain|what\s+does)\s+"
            r"(?:an?\s+|the\s+)?([a-z0-9/.-]{2,12})\??\s*$",
            user_message.strip(),
            re.IGNORECASE,
        )
        if not match:
            return None

        term = match.group(1).strip(" .?").lower()
        if not re.fullmatch(r"[a-z0-9/.-]{2,12}", term):
            return None

        # Only guard short acronym/code-like terms. Longer natural-language
        # questions should still be allowed through RAG+LLM.
        if len(term) > 6:
            return None

        if find_mainframe_memory_entries(term, limit=1):
            return None

        known_terms = get_known_mainframe_terms()
        suggestions = [
            suggestion
            for suggestion in get_close_matches(term, known_terms, n=3, cutoff=0.6)
            if len(suggestion) <= 24
        ]
        suggestion_text = ""
        if suggestions:
            suggestion_text = f"\n- Did you mean: {', '.join(f'`{s}`' for s in suggestions)}?"

        return (
            f"**{term.upper()}**\n"
            f"- I do not recognize `{term.upper()}` in the current mainframe glossary or RAG index."
            f"{suggestion_text}\n"
            "- I will not invent a definition.\n"
            f"- To teach me: click WRONG with the corrected answer, or add a safe original `### {term.upper()}` section to `data/rag_seed/mainframe_basics.md` and re-run RAG init."
        )

    def _unknown_definition_help_answer(
        self,
        user_message: str,
        rag_results: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[str]:
        """Give a useful non-invented answer for unknown definition questions."""
        target = self._extract_definition_target(user_message)
        if not target:
            return None

        suggestions = [
            suggestion
            for suggestion in get_close_matches(target.lower(), get_known_mainframe_terms(), n=4, cutoff=0.55)
            if len(suggestion) <= 32
        ]
        suggestion_text = ""
        if suggestions:
            suggestion_text = f"\n- Closest known terms: {', '.join(f'`{s}`' for s in suggestions)}"

        rag_hint = ""
        if rag_results:
            doc_names = []
            for result in rag_results[:3]:
                name = result.get("metadata", {}).get("doc_name", "")
                if name and name not in doc_names:
                    doc_names.append(name)
            if doc_names:
                rag_hint = f"\n- I found possible RAG context in: {', '.join(doc_names)}. Add a structured `### {target}` section if this should become a direct answer."

        return (
            f"**{target}**\n"
            "- I do not have a reliable direct definition for this yet."
            f"{suggestion_text}"
            f"{rag_hint}\n"
            "- I will not invent it. To teach me, click WRONG with the correct answer or add a safe original section to `data/rag_seed/mainframe_basics.md`, then re-run RAG init."
        )

    async def _answer_fast_mainframe_qa(self, user_message: str) -> tuple[str, bool, str, int]:
        """Answer short mainframe questions quickly without session history."""
        # Try fuzzy seed index first (fastest path)
        fuzzy_result = self._lookup_fuzzy_seed(user_message)
        if fuzzy_result and fuzzy_result.get("match"):
            match = fuzzy_result["match"]
            confidence = fuzzy_result.get("confidence", 1.0)

            # Format response
            response = format_seed_definition(match)

            if confidence < 0.9 and fuzzy_result.get("assumed_term"):
                response = f"(Assuming you meant {fuzzy_result['assumed_term']})\n\n{response}"

            return response, True, "rag_seed_direct", 1

        history_answer = self._answer_history_direct(user_message)
        if history_answer:
            return history_answer, True, "rag_seed_direct", 1

        abend_direct_answer = self._answer_abend_direct(user_message, [])
        if abend_direct_answer:
            return abend_direct_answer, False, "memory_direct", 0

        concept_direct_answer, concept_source = self._answer_concept_direct(user_message)
        if concept_direct_answer:
            used_chunks = 1 if concept_source == "rag_seed_direct" else 0
            return concept_direct_answer, concept_source == "rag_seed_direct", concept_source, used_chunks

        unknown_answer = self._unknown_short_concept_answer(user_message)
        if unknown_answer:
            return unknown_answer, False, "unknown_guard", 0

        rag_results = await self.get_rag_results(user_message, n_results=3)
        rag_chunks = len(rag_results)
        abend_direct_answer = self._answer_abend_direct(user_message, rag_results)
        if abend_direct_answer:
            abend_source = "rag_direct" if "Likely causes:" in abend_direct_answer else "memory_direct"
            used_chunks = rag_chunks if abend_source == "rag_direct" else 0
            return abend_direct_answer, abend_source == "rag_direct", abend_source, used_chunks

        rag_definition_answer = self._answer_rag_definition_direct(user_message, rag_results)
        if rag_definition_answer:
            return rag_definition_answer, True, "rag_direct", rag_chunks

        if self._is_definition_question(user_message):
            unknown_definition_answer = self._unknown_definition_help_answer(user_message, rag_results)
            if unknown_definition_answer:
                return unknown_definition_answer, bool(rag_results), "unknown_guard", rag_chunks if rag_results else 0

        # Log query miss for backlog before falling back to LLM
        if self._miss_tracker:
            suggestions = []
            if fuzzy_result and fuzzy_result.get("suggestions"):
                suggestions = [s["title"] for s in fuzzy_result["suggestions"]]
            self._miss_tracker.log_miss(user_message, "rag_llm", suggestions)

        rag_context = ""
        if rag_results:
            rag_context = "\n\n[Relevant Knowledge Base Information]\n"
            for r in rag_results:
                rag_context += f"---\n{r['content']}\n"
            reference_context = f"\n\nRAG context from local knowledge base:{rag_context}"
            context_source = "rag"
        else:
            memory_context = retrieve_mainframe_memory(user_message, limit=3)
            reference_context = f"\n\nFallback reference memory:\n{memory_context}" if memory_context else ""
            context_source = "fallback_memory" if memory_context else "none"

        prompt = (
            "Answer this mainframe question concisely in BigIron.ai style. "
            "Use mainframe-native terms. Do not generate JCL or code unless explicitly asked. "
            "For ABEND codes, include meaning, likely cause, and one evidence item to check. "
            "Use at most 4 short bullets or 80 words. Stop after the direct answer.\n\n"
            f"Question: {user_message}"
            f"{reference_context}"
        )
        response = await self.llm.chat_compact(
            [{"role": "user", "content": prompt}],
            system_prompt="You are BigIron.ai. Answer directly using mainframe-native terms.",
            temperature=0.2,
            max_tokens=140,
            timeout=45.0,
        )
        return response, bool(rag_context), context_source, rag_chunks
    
    async def process_command(self, command: str, args: str = "") -> Dict[str, Any]:
        """Process a slash command."""
        result = {
            "response": "",
            "connected": self.is_connected,
            "host": self.connection_host,
            "screen": None,
            "rag_used": False,
            "rag_chunks": 0,
            "context_source": "none",
            "answer_mode": "none",
            "model": self.config.OLLAMA_MODEL
        }
        
        if command == "/connect":
            if not args:
                result["response"] = "Usage: `/connect host:port`\n\nExample: `/connect localhost:3270`"
            elif self._connect_mainframe:
                success, message = self._connect_mainframe(args)
                result["response"] = message
                result["connected"] = self.is_connected
                result["host"] = self.connection_host
                result["screen"] = self.current_screen
            else:
                result["response"] = "Connection functionality not available."
        
        elif command == "/disconnect":
            if self._disconnect_mainframe:
                result["response"] = self._disconnect_mainframe()
            result["connected"] = False
            result["screen"] = None
        
        elif command == "/screen":
            if self.is_connected and self._read_screen:
                screen = self._read_screen()
                result["response"] = f"**Current Screen:**\n```\n{screen}\n```"
                result["screen"] = screen
            else:
                result["response"] = "Not connected. Use `/connect host:port` first."
        
        elif command == "/clear":
            self.clear_history()
            result["response"] = "Conversation cleared."
        
        elif command == "/model":
            if args:
                self.config.OLLAMA_MODEL = args
                result["response"] = f"Model changed to: `{args}`"
            else:
                result["response"] = f"Current model: `{self.config.OLLAMA_MODEL}`\n\nUsage: `/model llama3.1:8b`"
        
        elif command == "/help":
            result["response"] = """## Commands

| Command | Description |
|---------|-------------|
| `/connect host:port` | Connect to mainframe via TN3270 |
| `/disconnect` | Disconnect from mainframe |
| `/screen` | Show current 3270 screen |
| `/model [name]` | Show/change Ollama model |
| `/clear` | Clear conversation history |
| `/help` | Show this help |

## Terminal Shortcuts (when connected)
- **Enter** - Send Enter key
- **Esc** - Send Clear
- **F1-F12** - PF1-PF12
- **Shift+F1-F12** - PF13-PF24
- **Tab** - Next field
- **Ctrl+R** - Reset

## Example Questions
- What does ABEND S0C7 mean?
- Generate JCL to copy a dataset
- Explain this COBOL code: [paste code]"""
        
        else:
            result["response"] = f"Unknown command: `{command}`. Type `/help` for available commands."
        
        return result
    
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """Process a chat message."""
        result = {
            "response": "",
            "connected": self.is_connected,
            "host": self.connection_host,
            "screen": None,
            "rag_used": False,
            "rag_chunks": 0,
            "context_source": "none",
            "answer_mode": "none",
            "model": self.config.OLLAMA_MODEL
        }
        
        # Handle commands
        if user_message.startswith("/"):
            parts = user_message.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            return await self.process_command(cmd, args)

        if self._is_fast_mainframe_qa(user_message):
            response, rag_used, context_source, rag_chunks = await self._answer_fast_mainframe_qa(user_message)
            result["response"] = response
            result["rag_used"] = rag_used
            result["rag_chunks"] = rag_chunks
            result["context_source"] = context_source
            if context_source in ("rag_direct", "rag_seed_direct", "memory_direct", "unknown_guard"):
                result["answer_mode"] = context_source
            else:
                result["answer_mode"] = "rag_llm"
            return result
        
        # Check if any LLM provider is available
        if not await self.llm.check_available():
            result["response"] = """⚠️ **Local Ollama is not available.**

```bash
ollama serve
ollama pull mistral
ollama create bigiron-mistral -f configs/ollama/Modelfile.bigiron-mistral
```
"""
            return result
        
        # Build context. Keep general Q&A fast by not attaching the current
        # terminal screen unless the user asks about the live session.
        context = ""
        rag_context, rag_chunks = await self.get_rag_context_with_meta(user_message)
        result["rag_used"] = bool(rag_context)
        result["rag_chunks"] = rag_chunks
        result["context_source"] = "rag" if rag_context else "none"
        result["answer_mode"] = "llm"
        
        if self.is_connected and self._read_screen and self._should_include_screen_context(user_message):
            screen = self._read_screen()
            result["screen"] = screen
            context = f"\n\n[Current 3270 Screen]\n```\n{screen}\n```"
        
        full_message = user_message + rag_context + context
        
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Call local LLM.
        request_messages = self.conversation_history[-self.max_history:]
        if rag_context or context:
            request_messages = request_messages[:-1] + [{
                "role": "user",
                "content": full_message,
            }]

        assistant_message = await self.llm.chat_simple(request_messages, max_tokens=768)
        
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Cap history
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        
        result["response"] = assistant_message
        return result


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get the singleton chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
