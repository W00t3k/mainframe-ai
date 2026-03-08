#!/usr/bin/env python3
"""
Methodology Engine - Control Plane Assessment Framework

Implements the "Screen → Control Plane → Findings Area → Evidence → Next Action" workflow.

This is the core differentiator: a formalized assessment methodology that maps mainframe security
to five control planes, five broken assumptions, and five findings areas.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


# =============================================================================
# The 5 Control Planes
# =============================================================================

CONTROL_PLANES = {
    "VTAM": {
        "name": "Session Fabric",
        "description": "VTAM manages LU sessions independently of TCP/IP. Sessions outlive connections.",
        "indicators": [
            "VTAM", "USS", "LOGON", "APPLID", "NVAS", "IKJ56", "SESSION",
            "USSTAB", "USSMSG", "LOGMODE", "CLSDST", "VARY NET"
        ],
        "trust_boundary": "Network boundary - but sessions persist beyond TCP",
        "key_insight": "The session fabric exists before and after authentication"
    },
    "TSO": {
        "name": "Human Interaction Plane",
        "description": "TSO/ISPF is where identity binds to sessions. Address spaces persist.",
        "indicators": [
            "TSO", "ISPF", "READY", "IKJ", "LOGON", "LOGOFF", "RFE", "EDIT",
            "BROWSE", "SDSF", "DSLIST", "OPTION", "COMMAND", "PF"
        ],
        "trust_boundary": "Identity binding - userid becomes context for all actions",
        "key_insight": "Address spaces outlive individual commands; context persists"
    },
    "RACF": {
        "name": "Authorization Plane",
        "description": "RACF is the continuous authorization engine. Every subsystem queries it.",
        "indicators": [
            "RACF", "ICH", "PERMIT", "PROFILE", "CONNECT", "AUTHORITY",
            "ACCESS", "AUDIT", "SETROPTS", "ADDUSER", "ALTUSER", "LISTUSER"
        ],
        "trust_boundary": "Distributed authority - no root, profiles define access",
        "key_insight": "Authentication is not authorization; RACF evaluates every access"
    },
    "JES": {
        "name": "Deferred Execution Plane",
        "description": "JES brokers work declaration from execution. Jobs run later under submitter identity.",
        "indicators": [
            "JES", "JOB", "SDSF", "OUTPUT", "HELD", "ACTIVE", "INPUT",
            "JESMSGLG", "JESJCL", "SPOOL", "PURGE", "CANCEL", "SUBMIT"
        ],
        "trust_boundary": "Temporal boundary - execution happens after submission",
        "key_insight": "Work declared now executes later under the submitter's authority"
    },
    "CICS": {
        "name": "Transaction Execution Plane",
        "description": "CICS regions host online transactions. Programs run in shared address spaces.",
        "indicators": [
            "CICS", "CEMT", "CEDA", "CESN", "DFHSTART", "TRANSACTION",
            "REGION", "SYSID", "PCT", "PPT", "NEWCOPY"
        ],
        "trust_boundary": "Transaction boundary - shared region, program-level trust",
        "key_insight": "Many transactions share one address space; isolation is logical, not physical"
    }
}


# =============================================================================
# The 5 Broken Assumptions
# =============================================================================

BROKEN_ASSUMPTIONS = {
    "ROOT_USER": {
        "assumption": "There is a root user",
        "reality": "RACF distributes authority across profiles. No single account has unconditional access.",
        "trigger_patterns": ["SPECIAL", "OPERATIONS", "PERMIT", "AUTHORITY", "PROFILE"],
        "assessment_implication": "Look for profile coverage, not privilege escalation to root"
    },
    "SHORT_LIVED_PROCESSES": {
        "assumption": "Processes are short-lived",
        "reality": "Address spaces persist. TSO sessions, CICS regions, started tasks run for hours/days.",
        "trigger_patterns": ["LOGON", "REGION", "STARTED", "STC", "ADDRESS SPACE"],
        "assessment_implication": "Authority evaluated at startup may not reflect current policy"
    },
    "PORTS_DEFINE_EXPOSURE": {
        "assumption": "Ports define exposure",
        "reality": "VTAM sessions outlive TCP. The session fabric is the real attack surface.",
        "trigger_patterns": ["VTAM", "APPLID", "LU", "SESSION", "LOGMODE"],
        "assessment_implication": "Network scan won't reveal VTAM APPLIDs or session state"
    },
    "AUTH_EQUALS_AUTHZ": {
        "assumption": "Authentication = Authorization",
        "reality": "RACF separates these completely. Logging in grants no blanket access.",
        "trigger_patterns": ["LOGON", "PASSWORD", "ICH", "PERMIT", "NOT AUTHORIZED"],
        "assessment_implication": "Every resource access triggers a separate RACF check"
    },
    "IMMEDIATE_EXECUTION": {
        "assumption": "Work executes immediately",
        "reality": "JES brokers deferred execution. Jobs run later under submitter's identity.",
        "trigger_patterns": ["JOB", "SUBMIT", "JES", "SPOOL", "OUTPUT QUEUE"],
        "assessment_implication": "Ask: what work is queued? Under whose authority will it run?"
    }
}


# =============================================================================
# The 5 Findings Areas (F1–F5)
# =============================================================================

ASSESSMENT_QUESTIONS = {
    "Q1_IDENTITY_BINDING": {
        "question": "Where is identity bound?",
        "explanation": "At which point does a session become associated with a userid?",
        "relevant_planes": ["VTAM", "TSO", "CICS"],
        "evidence_types": ["LOGON screen", "TSO session", "CESN transaction"],
        "follow_up": "Is the current session authenticated? What identity context applies?"
    },
    "Q2_AUTHORITY_EVALUATION": {
        "question": "When is authority evaluated?",
        "explanation": "At what moment does RACF check if an action is permitted?",
        "relevant_planes": ["RACF", "TSO", "JES"],
        "evidence_types": ["ICH messages", "NOT AUTHORIZED", "PERMIT status"],
        "follow_up": "Was authority checked at session start, or on this specific action?"
    },
    "Q3_DEFERRED_EXECUTION": {
        "question": "What executes later than expected?",
        "explanation": "Is there work declared now that will run in the future?",
        "relevant_planes": ["JES", "TSO"],
        "evidence_types": ["SUBMIT command", "Job queue", "SDSF output"],
        "follow_up": "What jobs are pending? Under whose identity will they execute?"
    },
    "Q4_POLICY_ENFORCEMENT": {
        "question": "Which subsystem enforces policy?",
        "explanation": "Where is access control actually enforced for this action?",
        "relevant_planes": ["RACF", "TSO", "CICS", "JES"],
        "evidence_types": ["RACF profiles", "Subsystem messages", "Authority errors"],
        "follow_up": "Is the panel enforcing access, or is it delegating to RACF?"
    },
    "Q5_IMPORTED_ASSUMPTIONS": {
        "question": "What assumptions are you importing incorrectly?",
        "explanation": "Which Unix/cloud mental models don't apply here?",
        "relevant_planes": ["VTAM", "TSO", "RACF", "JES", "CICS"],
        "evidence_types": ["Any screen that violates expectations"],
        "follow_up": "What did you expect to see? Why is the reality different?"
    }
}


# =============================================================================
# Screen Analysis Result
# =============================================================================

@dataclass
class ScreenAnalysis:
    """Result of analyzing a TN3270 screen through the methodology engine."""
    
    # Step 1: Control Plane Classification
    control_plane: str
    control_plane_confidence: float
    control_plane_evidence: List[str]
    
    # Step 2: Broken Assumption Identification
    broken_assumption: Optional[str]
    assumption_evidence: List[str]
    
    # Step 3: Findings Area
    primary_question: str
    question_context: str
    
    # Step 4: Evidence Extraction
    extracted_evidence: Dict[str, List[str]]
    
    # Step 5: Next Action
    suggested_action: str
    action_rationale: str
    
    # Metadata
    analysis_timestamp: str = ""
    screen_hash: str = ""
    
    def __post_init__(self):
        if not self.analysis_timestamp:
            self.analysis_timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"## Control Plane: {self.control_plane}",
            f"*{CONTROL_PLANES.get(self.control_plane, {}).get('name', 'Unknown')}*",
            "",
            f"**Confidence:** {self.control_plane_confidence:.0%}",
            f"**Evidence:** {', '.join(self.extracted_evidence.get('indicators', [])[:5])}",
            "",
            f"## Assessment Question",
            f"**{ASSESSMENT_QUESTIONS.get(self.primary_question, {}).get('question', self.primary_question)}**",
            "",
            self.question_context,
            "",
        ]
        
        if self.broken_assumption:
            assumption = BROKEN_ASSUMPTIONS.get(self.broken_assumption, {})
            lines.extend([
                f"## Broken Assumption",
                f"**\"{assumption.get('assumption', self.broken_assumption)}\"**",
                "",
                assumption.get('reality', ''),
                "",
            ])
        
        lines.extend([
            f"## Suggested Action",
            f"**{self.suggested_action}**",
            "",
            self.action_rationale,
        ])
        
        return "\n".join(lines)


# =============================================================================
# Methodology Engine
# =============================================================================

class MethodologyEngine:
    """
    The core methodology engine implementing:
    Screen → Control Plane → Assessment Question → Evidence → Next Action
    """
    
    def __init__(self):
        self.analysis_history: List[ScreenAnalysis] = []
    
    def classify_control_plane(self, screen_text: str) -> Tuple[str, float, List[str]]:
        """
        Step 1: Classify which control plane the screen belongs to.
        Returns (plane_name, confidence, evidence_list).
        """
        screen_upper = screen_text.upper()
        scores: Dict[str, Tuple[int, List[str]]] = {}
        
        for plane_name, plane_info in CONTROL_PLANES.items():
            matches = []
            for indicator in plane_info["indicators"]:
                if indicator.upper() in screen_upper:
                    matches.append(indicator)
            scores[plane_name] = (len(matches), matches)
        
        # Find the plane with the most indicator matches
        best_plane = max(scores.keys(), key=lambda p: scores[p][0])
        best_score, best_matches = scores[best_plane]
        
        # Calculate confidence based on match count
        total_possible = len(CONTROL_PLANES[best_plane]["indicators"])
        confidence = min(best_score / max(total_possible * 0.3, 1), 1.0)
        
        # Default to TSO if nothing matches (most common interactive context)
        if best_score == 0:
            return "TSO", 0.3, ["Default: no specific indicators found"]
        
        return best_plane, confidence, best_matches
    
    def identify_broken_assumption(self, screen_text: str, control_plane: str) -> Tuple[Optional[str], List[str]]:
        """
        Step 2: Identify which broken assumption this screen reveals.
        Returns (assumption_key, evidence_list) or (None, []).
        """
        screen_upper = screen_text.upper()
        
        # Map control planes to their most relevant broken assumptions
        plane_assumption_priority = {
            "VTAM": ["PORTS_DEFINE_EXPOSURE", "AUTH_EQUALS_AUTHZ"],
            "TSO": ["SHORT_LIVED_PROCESSES", "AUTH_EQUALS_AUTHZ", "ROOT_USER"],
            "RACF": ["ROOT_USER", "AUTH_EQUALS_AUTHZ"],
            "JES": ["IMMEDIATE_EXECUTION", "SHORT_LIVED_PROCESSES"],
            "CICS": ["SHORT_LIVED_PROCESSES", "ROOT_USER"]
        }
        
        priority_list = plane_assumption_priority.get(control_plane, list(BROKEN_ASSUMPTIONS.keys()))
        
        for assumption_key in priority_list:
            assumption = BROKEN_ASSUMPTIONS[assumption_key]
            matches = []
            for pattern in assumption["trigger_patterns"]:
                if pattern.upper() in screen_upper:
                    matches.append(pattern)
            if matches:
                return assumption_key, matches
        
        return None, []
    
    def select_assessment_question(self, control_plane: str, broken_assumption: Optional[str]) -> Tuple[str, str]:
        """
        Step 3: Select the most relevant assessment question.
        Returns (question_key, context_explanation).
        """
        # Map control planes to primary questions
        plane_question_map = {
            "VTAM": "Q1_IDENTITY_BINDING",
            "TSO": "Q4_POLICY_ENFORCEMENT",
            "RACF": "Q2_AUTHORITY_EVALUATION",
            "JES": "Q3_DEFERRED_EXECUTION",
            "CICS": "Q4_POLICY_ENFORCEMENT"
        }
        
        # Map broken assumptions to questions
        assumption_question_map = {
            "ROOT_USER": "Q2_AUTHORITY_EVALUATION",
            "SHORT_LIVED_PROCESSES": "Q1_IDENTITY_BINDING",
            "PORTS_DEFINE_EXPOSURE": "Q5_IMPORTED_ASSUMPTIONS",
            "AUTH_EQUALS_AUTHZ": "Q2_AUTHORITY_EVALUATION",
            "IMMEDIATE_EXECUTION": "Q3_DEFERRED_EXECUTION"
        }
        
        # Prefer assumption-based question if available
        if broken_assumption and broken_assumption in assumption_question_map:
            question_key = assumption_question_map[broken_assumption]
        else:
            question_key = plane_question_map.get(control_plane, "Q5_IMPORTED_ASSUMPTIONS")
        
        question = ASSESSMENT_QUESTIONS[question_key]
        context = f"{question['explanation']} {question['follow_up']}"
        
        return question_key, context
    
    def extract_evidence(self, screen_text: str) -> Dict[str, List[str]]:
        """
        Step 4: Extract artifacts from the screen as evidence.
        """
        evidence: Dict[str, List[str]] = {
            "indicators": [],
            "userids": [],
            "datasets": [],
            "jobnames": [],
            "transactions": [],
            "messages": [],
            "panels": []
        }
        
        lines = screen_text.split('\n')
        
        for line in lines:
            line_upper = line.upper().strip()
            
            # Extract userids (common patterns)
            userid_match = re.findall(r'\b(HERC\d{2}|IBMUSER|[A-Z]{1,7}\d{1,2})\b', line_upper)
            evidence["userids"].extend(userid_match)
            
            # Extract dataset names (HLQ.qualifier.qualifier pattern)
            dataset_match = re.findall(r'\b([A-Z][A-Z0-9]{0,7}(?:\.[A-Z][A-Z0-9]{0,7})+)\b', line_upper)
            evidence["datasets"].extend([d for d in dataset_match if len(d) > 8])
            
            # Extract job names (8 char, ends in number or specific patterns)
            job_match = re.findall(r'\b([A-Z][A-Z0-9]{2,7})\s+(?:JOB\d{5}|ACTIVE|HELD|OUTPUT)', line_upper)
            evidence["jobnames"].extend(job_match)
            
            # Extract CICS transactions (4 char)
            if "CICS" in line_upper or "CEMT" in line_upper or "CEDA" in line_upper:
                trans_match = re.findall(r'\b([A-Z][A-Z0-9]{3})\b', line_upper)
                evidence["transactions"].extend(trans_match[:5])
            
            # Extract system messages (IKJ, ICH, IEF, etc.)
            msg_match = re.findall(r'\b(I[A-Z]{2}\d{3,5}[A-Z]?)\b', line_upper)
            evidence["messages"].extend(msg_match)
            
            # Track control plane indicators found
            for plane_info in CONTROL_PLANES.values():
                for indicator in plane_info["indicators"]:
                    if indicator.upper() in line_upper and indicator not in evidence["indicators"]:
                        evidence["indicators"].append(indicator)
        
        # Deduplicate
        for key in evidence:
            evidence[key] = list(dict.fromkeys(evidence[key]))[:10]
        
        return evidence
    
    def recommend_action(self, control_plane: str, question_key: str, evidence: Dict[str, List[str]]) -> Tuple[str, str]:
        """
        Step 5: Recommend the next assessment action.
        """
        actions = {
            ("VTAM", "Q1_IDENTITY_BINDING"): (
                "Type TSO to transition from session fabric to identity binding",
                "VTAM is the anonymous session layer. Identity has not yet been bound. Entering TSO initiates the authentication flow where RACF will bind a userid to this session."
            ),
            ("TSO", "Q1_IDENTITY_BINDING"): (
                "Complete logon to bind identity, then run LISTALC STATUS",
                "TSO logon binds your userid to the address space. LISTALC shows the resource context of your identity—which datasets and libraries are allocated to your session."
            ),
            ("TSO", "Q4_POLICY_ENFORCEMENT"): (
                "Navigate to a dataset or execute a command to observe RACF enforcement",
                "Every action in TSO triggers a RACF check. Try browsing a dataset you don't own to see the authorization boundary in action."
            ),
            ("RACF", "Q2_AUTHORITY_EVALUATION"): (
                "Run LISTUSER or examine ICH messages for authority evidence",
                "RACF messages (ICH*) reveal the authority model. LISTUSER shows your profile attributes. Look for SPECIAL, OPERATIONS, or group connections."
            ),
            ("JES", "Q3_DEFERRED_EXECUTION"): (
                "Check SDSF output queue (O) and held queue (H) for pending work",
                "JES separates job declaration from execution. The output queue shows what has run; the input queue shows what will run. Both carry the submitter's identity."
            ),
            ("CICS", "Q4_POLICY_ENFORCEMENT"): (
                "Use CEMT I TASK to inspect running transactions",
                "CICS transactions share an address space but have logical isolation. CEMT reveals what's running and under what transaction security context."
            )
        }
        
        key = (control_plane, question_key)
        if key in actions:
            return actions[key]
        
        # Default action
        return (
            "Continue exploring to gather more evidence",
            f"You are in the {control_plane} control plane. Observe the screen for authority indicators, identity context, and subsystem boundaries."
        )
    
    def analyze_screen(self, screen_text: str) -> ScreenAnalysis:
        """
        Main entry point: Analyze a screen through the full methodology workflow.
        
        Screen → Control Plane → Assessment Question → Evidence → Next Action
        """
        import hashlib
        screen_hash = hashlib.md5(screen_text.encode()).hexdigest()[:12]
        
        # Step 1: Control Plane Classification
        control_plane, confidence, plane_evidence = self.classify_control_plane(screen_text)
        
        # Step 2: Broken Assumption Identification
        broken_assumption, assumption_evidence = self.identify_broken_assumption(screen_text, control_plane)
        
        # Step 3: Assessment Question Selection
        question_key, question_context = self.select_assessment_question(control_plane, broken_assumption)
        
        # Step 4: Evidence Extraction
        extracted_evidence = self.extract_evidence(screen_text)
        extracted_evidence["indicators"] = plane_evidence  # Include classification evidence
        
        # Step 5: Next Action Recommendation
        suggested_action, action_rationale = self.recommend_action(control_plane, question_key, extracted_evidence)
        
        # Build result
        analysis = ScreenAnalysis(
            control_plane=control_plane,
            control_plane_confidence=confidence,
            control_plane_evidence=plane_evidence,
            broken_assumption=broken_assumption,
            assumption_evidence=assumption_evidence,
            primary_question=question_key,
            question_context=question_context,
            extracted_evidence=extracted_evidence,
            suggested_action=suggested_action,
            action_rationale=action_rationale,
            screen_hash=screen_hash
        )
        
        self.analysis_history.append(analysis)
        return analysis
    
    def get_control_plane_info(self, plane_name: str) -> Optional[Dict]:
        """Get detailed info about a control plane."""
        return CONTROL_PLANES.get(plane_name)
    
    def get_assumption_info(self, assumption_key: str) -> Optional[Dict]:
        """Get detailed info about a broken assumption."""
        return BROKEN_ASSUMPTIONS.get(assumption_key)
    
    def get_question_info(self, question_key: str) -> Optional[Dict]:
        """Get detailed info about an assessment question."""
        return ASSESSMENT_QUESTIONS.get(question_key)
    
    def get_methodology_summary(self) -> Dict:
        """Return the complete methodology framework as a dict."""
        return {
            "control_planes": CONTROL_PLANES,
            "broken_assumptions": BROKEN_ASSUMPTIONS,
            "assessment_questions": ASSESSMENT_QUESTIONS,
            "analysis_count": len(self.analysis_history)
        }


# =============================================================================
# Module-level instance
# =============================================================================

_engine: Optional[MethodologyEngine] = None


def get_methodology_engine() -> MethodologyEngine:
    """Get or create the singleton methodology engine instance."""
    global _engine
    if _engine is None:
        _engine = MethodologyEngine()
    return _engine


def analyze_screen(screen_text: str) -> ScreenAnalysis:
    """Convenience function to analyze a screen."""
    return get_methodology_engine().analyze_screen(screen_text)


# =============================================================================
# CLI Test
# =============================================================================

if __name__ == "__main__":
    # Test with sample VTAM screen
    vtam_screen = """
    NVAS     z/OS V2R5 - Network Access
    
    ==> Enter a command or logon ID
    
    Enter LOGON followed by your logon ID
    or enter an application name
    
    Applications available:
    TSO      - Time Sharing Option
    CICS     - Customer Information Control System
    """
    
    engine = get_methodology_engine()
    result = engine.analyze_screen(vtam_screen)
    print(result.to_summary())
    print("\n---\n")
    
    # Test with TSO screen
    tso_screen = """
    READY
    LISTALC STATUS
    
    HERC01.PROFILE.EXEC        KEEP     SHR
    SYS1.CMDLIB                KEEP     SHR
    SYS1.LINKLIB               KEEP     SHR
    ISPF.ISPFLIB               KEEP     SHR
    
    IKJ56455I HERC01 LOGGED ON
    """
    
    result2 = engine.analyze_screen(tso_screen)
    print(result2.to_summary())
