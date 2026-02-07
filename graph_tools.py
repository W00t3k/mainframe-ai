#!/usr/bin/env python3
"""
Graph Tools - Parsers and agent loops for building the trust graph
Includes: classify_panel, extract_identifiers, parse_jcl, parse_sysout
Agent loops: Screen Mapper, Batch Trust, CICS Relationship
"""

import re
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime

# Helpers for parsing z/OS output (optional)
TSO_HELPER = None
CICS_HELPER = None
JES_PARSER = None

from trust_graph import get_trust_graph, TrustGraph


# =============================================================================
# Regex Patterns
# =============================================================================

# Dataset name: 1-44 chars, qualifiers separated by dots
DATASET_PATTERN = re.compile(r"[A-Z@#$][A-Z0-9@#$]{0,7}(?:\.[A-Z@#$][A-Z0-9@#$]{0,7}){0,21}")

# Job ID: JOBnnnnn or Jnnnnnnn
JOBID_PATTERN = re.compile(r"JOB\d{5}|J\d{7}")

# Job name: 1-8 alphanumeric starting with letter
JOBNAME_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{0,7}\b")

# CICS/KICKS transaction: 4 chars
TRANS_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{3}\b")

# Program name: 1-8 chars
PROGRAM_PATTERN = re.compile(r"\b[A-Z@#$][A-Z0-9@#$]{0,7}\b")

# ABEND codes: Snnn or Unnnnnn
ABEND_PATTERN = re.compile(r"\b[SU][0-9A-F]{3,4}\b")

# Message IDs: IEFnnnI, DFHnnnnI, etc.
MESSAGE_PATTERN = re.compile(r"\b[A-Z]{3}\d{3,5}[A-Z]?\b")

# PF key labels: PF1=HELP, F3=END
PF_KEY_PATTERN = re.compile(r"(?:PF|F)(\d{1,2})=([A-Z]+)")

# APPLID pattern
APPLID_PATTERN = re.compile(r"APPLID[=:\s]+([A-Z][A-Z0-9]{1,7})")

# User ID: 1-8 chars
USERID_PATTERN = re.compile(r"\bUSERID[=:\s]+([A-Z][A-Z0-9]{0,7})\b", re.IGNORECASE)


# =============================================================================
# Panel Classification
# =============================================================================

def classify_panel(screen_text: str) -> Dict:
    """Classify a 3270 screen into a panel type.

    Uses pattern matching to identify panel types.

    Returns:
        {
            "panel_type": str,
            "panel_id": str | None,
            "title": str,
            "environment": str,
            "has_command_line": bool,
            "available_pf_keys": list,
            "input_field_count": int,
            "applid": str | None
        }
    """
    result = {
        "panel_type": "UNKNOWN",
        "panel_id": None,
        "title": "",
        "environment": "UNKNOWN",
        "has_command_line": False,
        "available_pf_keys": [],
        "input_field_count": 0,
        "applid": None
    }

    upper = screen_text.upper()

    # Detect environment
    if TSO_HELPER and TSO_HELPER.detect_tso_screen(screen_text):
        result["environment"] = "TSO"
        panel_type = TSO_HELPER.detect_ispf_panel(screen_text)

        if panel_type == "PRIMARY":
            result["panel_type"] = "ISPF_PRIMARY"
            result["title"] = "ISPF Primary Option Menu"
        elif panel_type == "EDIT":
            result["panel_type"] = "ISPF_EDIT"
            result["title"] = "ISPF Edit"
        elif panel_type == "BROWSE":
            result["panel_type"] = "ISPF_BROWSE"
            result["title"] = "ISPF Browse"
        elif panel_type == "DSLIST":
            result["panel_type"] = "ISPF_DSLIST"
            result["title"] = "Dataset List Utility"
        elif panel_type == "UTILITIES":
            result["panel_type"] = "ISPF_UTILITIES"
            result["title"] = "ISPF Utilities"
        elif panel_type == "MEMBER":
            result["panel_type"] = "ISPF_MEMBER_LIST"
            result["title"] = "Member List"
        elif "READY" in upper:
            result["panel_type"] = "TSO_READY"
            result["title"] = "TSO Ready"
        else:
            result["panel_type"] = "TSO_OTHER"

    elif CICS_HELPER and CICS_HELPER.detect_cics_screen(screen_text):
        result["environment"] = "CICS"

        if "CESN" in upper or "SIGN ON" in upper:
            result["panel_type"] = "CICS_CESN"
            result["title"] = "CICS Sign-on"
        elif "CEMT" in upper and ("INQUIRE" in upper or "INQ" in upper):
            result["panel_type"] = "CICS_CEMT"
            result["title"] = "CICS Master Terminal"
        elif "CEDA" in upper:
            result["panel_type"] = "CICS_CEDA"
            result["title"] = "CICS Resource Definition"
        elif "CEDF" in upper:
            result["panel_type"] = "CICS_CEDF"
            result["title"] = "CICS Execution Diagnostic"
        else:
            result["panel_type"] = "CICS_OTHER"

    # KICKS (CICS-compatible) detection
    elif "KICKS" in upper or "KSGM" in upper or "KSSF" in upper:
        result["environment"] = "KICKS"
        result["panel_type"] = "KICKS_TRANSACTION"
        result["title"] = "KICKS Transaction Processing"

    elif JES_PARSER and JES_PARSER.detect_jes_screen(screen_text):
        result["environment"] = "JES"
        result["panel_type"] = "JES_SDSF"
        result["title"] = "SDSF Display"

    elif "VTAM" in upper or "WELCOME" in upper or "LOGON" in upper:
        result["environment"] = "VTAM"
        result["panel_type"] = "VTAM_LOGON"
        result["title"] = "VTAM Logon"

    # Command line detection
    if "COMMAND ===>" in upper or "OPTION ===>" in upper or "===>" in screen_text:
        result["has_command_line"] = True

    # Extract PF keys shown
    pf_matches = PF_KEY_PATTERN.findall(screen_text)
    result["available_pf_keys"] = [f"PF{m[0]}={m[1]}" for m in pf_matches]

    # Extract APPLID
    applid_match = APPLID_PATTERN.search(screen_text)
    if applid_match:
        result["applid"] = applid_match.group(1)

    # Try to extract panel ID (varies by system)
    # Look for common patterns like "Panel: XXX" or "ISPF X.X"
    panel_id_match = re.search(r"Panel[:\s]+([A-Z0-9@#$]+)", screen_text)
    if panel_id_match:
        result["panel_id"] = panel_id_match.group(1)

    # Count potential input fields (rough estimate from underscores/dots)
    input_indicators = screen_text.count("____") + screen_text.count("....")
    result["input_field_count"] = input_indicators

    return result


# =============================================================================
# Identifier Extraction
# =============================================================================

def extract_identifiers(screen_text: str) -> Dict:
    """Extract all identifiable mainframe entities from screen text.

    Returns:
        {
            "datasets": list,
            "programs": list,
            "transactions": list,
            "jobnames": list,
            "jobids": list,
            "applids": list,
            "userids": list,
            "commands": list,
            "message_ids": list,
            "abend_codes": list,
            "pf_keys_shown": list
        }
    """
    result = {
        "datasets": [],
        "programs": [],
        "transactions": [],
        "jobnames": [],
        "jobids": [],
        "applids": [],
        "userids": [],
        "commands": [],
        "message_ids": [],
        "abend_codes": [],
        "pf_keys_shown": []
    }

    # Datasets - look for dotted names
    ds_matches = DATASET_PATTERN.findall(screen_text.upper())
    # Filter: must have at least one dot, exclude common false positives
    false_positives = {"OPTION", "COMMAND", "ENTER", "SCROLL", "UTILITY"}
    for ds in ds_matches:
        if "." in ds and ds.split(".")[0] not in false_positives:
            if ds not in result["datasets"]:
                result["datasets"].append(ds)

    # Job IDs
    result["jobids"] = list(set(JOBID_PATTERN.findall(screen_text.upper())))

    # ABEND codes
    result["abend_codes"] = list(set(ABEND_PATTERN.findall(screen_text.upper())))

    # Message IDs
    result["message_ids"] = list(set(MESSAGE_PATTERN.findall(screen_text.upper())))

    # PF keys
    pf_matches = PF_KEY_PATTERN.findall(screen_text)
    result["pf_keys_shown"] = [f"PF{m[0]}={m[1]}" for m in pf_matches]

    # APPLIDs
    applid_matches = APPLID_PATTERN.findall(screen_text)
    result["applids"] = list(set(applid_matches))

    # User IDs
    userid_matches = USERID_PATTERN.findall(screen_text)
    result["userids"] = list(set(userid_matches))

    # Transactions (4-char codes in CICS/KICKS context)
    # Only extract if screen looks like CICS or KICKS
    if (CICS_HELPER and CICS_HELPER.detect_cics_screen(screen_text)) or "KICKS" in screen_text.upper():
        # Look for transaction patterns
        trans_candidates = TRANS_PATTERN.findall(screen_text.upper())
        known_trans = {"CEMT", "CEDA", "CECI", "CEDF", "CESN", "CESF", "CEBR", 
                       "KSGM", "KSSF", "MENU", "INQ1", "MNT1", "ORD1"}  # KICKS transactions
        result["transactions"] = [t for t in trans_candidates if t in known_trans or len(t) == 4]

    # Commands - look for lines with ===> followed by text
    cmd_matches = re.findall(r"===>\s*(.+?)(?:\s{2,}|$)", screen_text)
    result["commands"] = [c.strip() for c in cmd_matches if c.strip()]

    return result


# =============================================================================
# JCL Parser
# =============================================================================

def parse_jcl(jcl_text: str) -> Dict:
    """Parse JCL text into structured job/step/DD representation.

    Handles:
    - JOB statement with parameters
    - EXEC statements (PGM= and PROC=)
    - DD statements with DSN, DISP, DCB, SPACE
    - Continuation lines

    Returns:
        {
            "jobname": str,
            "job_params": dict,
            "steps": list[{stepname, pgm, proc, cond, dds}],
            "procs_referenced": list,
            "datasets_referenced": list,
            "programs_referenced": list,
            "loadlibs": list
        }
    """
    result = {
        "jobname": None,
        "job_params": {},
        "steps": [],
        "procs_referenced": [],
        "datasets_referenced": [],
        "programs_referenced": [],
        "loadlibs": [],
        "parse_errors": []
    }

    # Join continuation lines (lines ending with comma and continued on next line starting with //)
    lines = jcl_text.split("\n")
    joined_lines = []
    current_line = ""

    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("//*"):
            # Comment line
            continue
        if stripped.startswith("//"):
            if current_line and current_line.rstrip().endswith(","):
                # Continuation
                current_line = current_line.rstrip() + " " + stripped[2:].lstrip()
            else:
                if current_line:
                    joined_lines.append(current_line)
                current_line = stripped
        elif current_line and stripped.startswith(" ") and current_line.rstrip().endswith(","):
            # Continuation without //
            current_line = current_line.rstrip() + " " + stripped.lstrip()
        elif stripped:
            if current_line:
                joined_lines.append(current_line)
                current_line = ""

    if current_line:
        joined_lines.append(current_line)

    current_step = None

    for line in joined_lines:
        upper = line.upper()

        # JOB statement
        job_match = re.match(r"//([A-Z@#$][A-Z0-9@#$]*)\s+JOB\s*(.*)", upper)
        if job_match:
            result["jobname"] = job_match.group(1)
            params_str = job_match.group(2)

            # Parse common JOB params
            class_match = re.search(r"CLASS=([A-Z0-9])", params_str)
            if class_match:
                result["job_params"]["class"] = class_match.group(1)

            msgclass_match = re.search(r"MSGCLASS=([A-Z0-9])", params_str)
            if msgclass_match:
                result["job_params"]["msgclass"] = msgclass_match.group(1)

            notify_match = re.search(r"NOTIFY=([A-Z0-9&]+)", params_str)
            if notify_match:
                result["job_params"]["notify"] = notify_match.group(1)

            continue

        # EXEC statement
        exec_match = re.match(r"//([A-Z@#$][A-Z0-9@#$]*)\s+EXEC\s+(.*)", upper)
        if exec_match:
            step_name = exec_match.group(1)
            exec_params = exec_match.group(2)

            step = {
                "stepname": step_name,
                "pgm": None,
                "proc": None,
                "cond": None,
                "dds": []
            }

            # PGM=
            pgm_match = re.search(r"PGM=([A-Z@#$][A-Z0-9@#$]*)", exec_params)
            if pgm_match:
                step["pgm"] = pgm_match.group(1)
                if step["pgm"] not in result["programs_referenced"]:
                    result["programs_referenced"].append(step["pgm"])

            # PROC=
            proc_match = re.search(r"PROC=([A-Z@#$][A-Z0-9@#$]*)", exec_params)
            if proc_match:
                step["proc"] = proc_match.group(1)
                if step["proc"] not in result["procs_referenced"]:
                    result["procs_referenced"].append(step["proc"])

            # Bare proc name (EXEC MYPROC)
            if not step["pgm"] and not step["proc"]:
                bare_match = re.match(r"([A-Z@#$][A-Z0-9@#$]*)", exec_params)
                if bare_match:
                    step["proc"] = bare_match.group(1)
                    if step["proc"] not in result["procs_referenced"]:
                        result["procs_referenced"].append(step["proc"])

            # COND=
            cond_match = re.search(r"COND=\(([^)]+)\)", exec_params)
            if cond_match:
                step["cond"] = cond_match.group(1)

            result["steps"].append(step)
            current_step = step
            continue

        # DD statement
        dd_match = re.match(r"//([A-Z@#$][A-Z0-9@#$]*)\s+DD\s*(.*)", upper)
        if dd_match and current_step:
            dd_name = dd_match.group(1)
            dd_params = dd_match.group(2)

            dd = {
                "ddname": dd_name,
                "dsname": None,
                "disp": None,
                "disp_normal": None,
                "disp_abnormal": None,
                "is_input": False,
                "is_output": False,
                "dcb": {},
                "space": None
            }

            # DSN=
            dsn_match = re.search(r"DSN=([A-Z@#$.&][A-Z0-9@#$.&()*+-]*)", dd_params)
            if dsn_match:
                dsname = dsn_match.group(1)
                # Remove member name if present
                if "(" in dsname:
                    dsname = dsname.split("(")[0]
                dd["dsname"] = dsname
                if dsname not in result["datasets_referenced"]:
                    result["datasets_referenced"].append(dsname)

            # DISP=
            disp_match = re.search(r"DISP=\(([^)]+)\)|DISP=([A-Z]+)", dd_params)
            if disp_match:
                disp_val = disp_match.group(1) or disp_match.group(2)
                dd["disp"] = disp_val

                disp_parts = disp_val.split(",")
                status = disp_parts[0] if disp_parts else ""

                # Determine input vs output
                if status in ("SHR", "OLD"):
                    dd["is_input"] = True
                elif status in ("NEW", "MOD"):
                    dd["is_output"] = True

                if len(disp_parts) > 1:
                    dd["disp_normal"] = disp_parts[1]
                if len(disp_parts) > 2:
                    dd["disp_abnormal"] = disp_parts[2]

            # DCB params
            recfm_match = re.search(r"RECFM=([A-Z]+)", dd_params)
            if recfm_match:
                dd["dcb"]["recfm"] = recfm_match.group(1)

            lrecl_match = re.search(r"LRECL=(\d+)", dd_params)
            if lrecl_match:
                dd["dcb"]["lrecl"] = lrecl_match.group(1)

            blksize_match = re.search(r"BLKSIZE=(\d+)", dd_params)
            if blksize_match:
                dd["dcb"]["blksize"] = blksize_match.group(1)

            # SPACE=
            space_match = re.search(r"SPACE=\(([^)]+)\)", dd_params)
            if space_match:
                dd["space"] = space_match.group(1)

            # Check for STEPLIB/JOBLIB (loadlibs)
            if dd_name in ("STEPLIB", "JOBLIB") and dd["dsname"]:
                if dd["dsname"] not in result["loadlibs"]:
                    result["loadlibs"].append(dd["dsname"])

            current_step["dds"].append(dd)

    return result


# =============================================================================
# SYSOUT Parser
# =============================================================================

def parse_sysout(sysout_text: str) -> Dict:
    """Parse SYSOUT/JES output into structured results.

    Extends JESParser functionality.

    Returns:
        {
            "jobname": str,
            "jobid": str,
            "steps": list[{stepname, procstep, pgm, return_code, abend_code, ...}],
            "overall_rc": str,
            "overall_abend": str,
            "ief_messages": list,
            "iec_messages": list,
            "ich_messages": list,
            "datasets_allocated": list,
            "datasets_created": list
        }
    """
    result = {
        "jobname": None,
        "jobid": None,
        "steps": [],
        "overall_rc": None,
        "overall_abend": None,
        "ief_messages": [],
        "iec_messages": [],
        "ich_messages": [],
        "datasets_allocated": [],
        "datasets_created": []
    }

    # Use JES parser if available
    if JES_PARSER:
        basic = JES_PARSER.parse_job_output(sysout_text)
        result["jobname"] = basic.get("jobname")
        result["jobid"] = basic.get("jobid")
        result["overall_rc"] = basic.get("return_code")

    lines = sysout_text.split("\n")
    current_step = None

    for line in lines:
        upper = line.upper()

        # Job ID extraction
        jobid_match = JOBID_PATTERN.search(upper)
        if jobid_match and not result["jobid"]:
            result["jobid"] = jobid_match.group()

        # Step execution messages
        # IEF142I - Step terminated
        if "IEF142I" in upper or "IEF404I" in upper:
            step_match = re.search(r"([A-Z@#$][A-Z0-9@#$]*)\s+-\s+STEP", upper)
            if step_match:
                step = {
                    "stepname": step_match.group(1),
                    "procstep": None,
                    "pgm": None,
                    "return_code": None,
                    "abend_code": None,
                    "cpu_time": None,
                    "datasets_allocated": [],
                    "datasets_created": []
                }
                result["steps"].append(step)
                current_step = step

        # Return codes
        if "COND CODE" in upper:
            rc_match = re.search(r"COND CODE\s+(\d{4})", upper)
            if rc_match:
                rc = rc_match.group(1)
                if current_step:
                    current_step["return_code"] = rc
                result["overall_rc"] = rc

        # ABEND codes
        abend_match = ABEND_PATTERN.search(upper)
        if abend_match:
            abend = abend_match.group()
            if current_step:
                current_step["abend_code"] = abend
            result["overall_abend"] = abend

        # Message collection
        if "IEF" in upper:
            result["ief_messages"].append(line.strip())
        if "IEC" in upper:
            result["iec_messages"].append(line.strip())
        if "ICH" in upper:
            result["ich_messages"].append(line.strip())

        # Dataset allocation (IEF285I)
        if "IEF285I" in upper:
            ds_match = DATASET_PATTERN.search(upper)
            if ds_match:
                ds = ds_match.group()
                if ds not in result["datasets_allocated"]:
                    result["datasets_allocated"].append(ds)
                if current_step and ds not in current_step["datasets_allocated"]:
                    current_step["datasets_allocated"].append(ds)

        # Dataset creation (look for CATLG in disposition)
        if "CATLG" in upper and "IEF285I" in upper:
            ds_match = DATASET_PATTERN.search(upper)
            if ds_match:
                ds = ds_match.group()
                if ds not in result["datasets_created"]:
                    result["datasets_created"].append(ds)
                if current_step and ds not in current_step["datasets_created"]:
                    current_step["datasets_created"].append(ds)

    return result


# =============================================================================
# Graph Update Helper
# =============================================================================

def update_graph_from_jcl(graph: TrustGraph, jcl_result: Dict,
                          evidence: Dict = None) -> Dict:
    """Update the trust graph from parsed JCL.

    Args:
        graph: TrustGraph instance
        jcl_result: Output from parse_jcl()
        evidence: Optional evidence dict

    Returns:
        Stats dict with counts of nodes/edges added
    """
    stats = {"nodes_added": 0, "edges_added": 0}
    evidence = evidence or {"type": "jcl", "timestamp": datetime.now().isoformat()}

    if not jcl_result.get("jobname"):
        return stats

    # Add Job node
    job_id = graph.add_node(
        "Job",
        jcl_result["jobname"],
        properties={"class": jcl_result["job_params"].get("class")},
        evidence=evidence
    )
    stats["nodes_added"] += 1

    # Add loadlibs
    for lib in jcl_result.get("loadlibs", []):
        lib_id = graph.add_node("Loadlib", lib, evidence=evidence)
        stats["nodes_added"] += 1

    # Process steps
    for step in jcl_result.get("steps", []):
        # Program
        if step.get("pgm"):
            pgm_id = graph.add_node(
                "Program",
                step["pgm"],
                properties={"step": step["stepname"]},
                evidence=evidence
            )
            stats["nodes_added"] += 1

            # EXECUTES edge
            graph.add_edge("EXECUTES", job_id, pgm_id, {"step": step["stepname"]}, evidence)
            stats["edges_added"] += 1

            # LOADS_FROM edges for loadlibs
            for lib in jcl_result.get("loadlibs", []):
                lib_id = graph.make_node_id("Loadlib", lib)
                graph.add_edge("LOADS_FROM", pgm_id, lib_id, evidence=evidence)
                stats["edges_added"] += 1

        # Proc
        if step.get("proc"):
            proc_id = graph.add_node("Proc", step["proc"], evidence=evidence)
            stats["nodes_added"] += 1
            graph.add_edge("CALLS_PROC", job_id, proc_id, evidence=evidence)
            stats["edges_added"] += 1

        # Datasets
        for dd in step.get("dds", []):
            if dd.get("dsname") and not dd["dsname"].startswith("&"):
                ds_id = graph.add_node(
                    "Dataset",
                    dd["dsname"],
                    properties={"ddname": dd["ddname"]},
                    evidence=evidence
                )
                stats["nodes_added"] += 1

                if dd.get("is_input"):
                    graph.add_edge("READS", job_id, ds_id,
                                   {"ddname": dd["ddname"], "disp": dd.get("disp")}, evidence)
                    stats["edges_added"] += 1

                if dd.get("is_output"):
                    graph.add_edge("WRITES", job_id, ds_id,
                                   {"ddname": dd["ddname"], "disp": dd.get("disp")}, evidence)
                    stats["edges_added"] += 1

    return stats


def update_graph_from_sysout(graph: TrustGraph, sysout_result: Dict,
                             evidence: Dict = None) -> Dict:
    """Update the trust graph from parsed SYSOUT.

    Args:
        graph: TrustGraph instance
        sysout_result: Output from parse_sysout()
        evidence: Optional evidence dict

    Returns:
        Stats dict
    """
    stats = {"nodes_added": 0, "edges_added": 0}
    evidence = evidence or {"type": "sysout", "timestamp": datetime.now().isoformat()}

    if not sysout_result.get("jobname"):
        return stats

    job_id = graph.add_node(
        "Job",
        sysout_result["jobname"],
        properties={"jobid": sysout_result.get("jobid")},
        evidence=evidence
    )
    stats["nodes_added"] += 1

    # Return codes and ABENDs
    if sysout_result.get("overall_abend"):
        rc_id = graph.add_node(
            "ReturnCode",
            sysout_result["overall_abend"],
            properties={"type": "ABEND"},
            evidence=evidence
        )
        stats["nodes_added"] += 1
        graph.add_edge("RETURNED", job_id, rc_id, evidence=evidence)
        stats["edges_added"] += 1

    elif sysout_result.get("overall_rc"):
        rc_id = graph.add_node(
            "ReturnCode",
            sysout_result["overall_rc"],
            properties={"type": "RC"},
            evidence=evidence
        )
        stats["nodes_added"] += 1
        graph.add_edge("RETURNED", job_id, rc_id, evidence=evidence)
        stats["edges_added"] += 1

    # Datasets from SYSOUT
    for ds in sysout_result.get("datasets_allocated", []):
        ds_id = graph.add_node("Dataset", ds, evidence=evidence)
        stats["nodes_added"] += 1

    return stats


def update_graph_from_screen(graph: TrustGraph, screen_text: str,
                             previous_panel_id: str = None,
                             action_taken: Dict = None) -> Dict:
    """Update the trust graph from a screen capture.

    Args:
        graph: TrustGraph instance
        screen_text: Raw screen text
        previous_panel_id: ID of previous panel node (for navigation edges)
        action_taken: Dict with action info (pf_key, command, etc.)

    Returns:
        Stats dict + current panel node ID
    """
    stats = {"nodes_added": 0, "edges_added": 0, "panel_id": None}

    panel_info = classify_panel(screen_text)
    identifiers = extract_identifiers(screen_text)

    evidence = {
        "type": "screen",
        "timestamp": datetime.now().isoformat(),
        "screen_hash": hashlib.md5(screen_text.encode()).hexdigest()[:8]
    }

    # Create panel node
    panel_label = panel_info.get("panel_id") or panel_info.get("panel_type", "UNKNOWN")
    panel_id = graph.add_node(
        "Panel",
        panel_label,
        properties={
            "panel_type": panel_info.get("panel_type"),
            "title": panel_info.get("title"),
            "environment": panel_info.get("environment"),
            "applid": panel_info.get("applid")
        },
        evidence=evidence
    )
    stats["nodes_added"] += 1
    stats["panel_id"] = panel_id

    # Navigation edge from previous panel
    if previous_panel_id and previous_panel_id != panel_id:
        edge_props = {}
        if action_taken:
            edge_props["pf_key"] = action_taken.get("pf_key")
            edge_props["command"] = action_taken.get("command")
        graph.add_edge("NAVIGATES_TO", previous_panel_id, panel_id, edge_props, evidence)
        stats["edges_added"] += 1

    # Add identified datasets
    for ds in identifiers.get("datasets", []):
        ds_id = graph.add_node("Dataset", ds, evidence=evidence)
        stats["nodes_added"] += 1

    # Add identified transactions (if CICS/KICKS)
    for trans in identifiers.get("transactions", []):
        trans_id = graph.add_node("Transaction", trans, evidence=evidence)
        stats["nodes_added"] += 1

        # If we have an APPLID, link transaction to region
        if panel_info.get("applid"):
            region_id = graph.add_node("CICSRegion", panel_info["applid"], evidence=evidence)
            graph.add_edge("RUNS_IN", trans_id, region_id, evidence=evidence)
            stats["edges_added"] += 1

    # Check for job submission indicators
    if "SUBMIT" in screen_text.upper() or panel_info.get("panel_type") == "ISPF_SUBMIT":
        # Mark this panel as a job submission point
        graph.nodes[panel_id].properties["submits_jobs"] = True

    return stats


# =============================================================================
# Finding Generator
# =============================================================================

def generate_finding(title: str, evidence: List[Dict], reasoning: str,
                     confidence: str, graph_path: List[str] = None,
                     affected_nodes: List[str] = None,
                     severity: str = "MEDIUM",
                     graph_context: Dict = None) -> Dict:
    """Generate a structured defensive finding.

    Args:
        title: Finding title
        evidence: List of evidence dicts
        reasoning: Explanation of why this is significant
        confidence: "HIGH", "MEDIUM", or "LOW"
        graph_path: List of node labels showing the path
        affected_nodes: List of affected node IDs
        severity: "HIGH", "MEDIUM", "LOW", or "INFO"

    Returns:
        Structured finding dict
    """
    import uuid

    finding_id = f"MTG-{datetime.now().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"

    return {
        "id": finding_id,
        "title": title,
        "severity": severity,
        "evidence": evidence,
        "reasoning": reasoning,
        "confidence": confidence,
        "affected_nodes": affected_nodes or [],
        "graph_path": graph_path or [],
        "defensive_verification": [],  # Filled in by caller
        "graph_context": graph_context or {},
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# Screen Mapper Agent
# =============================================================================

class ScreenMapperAgent:
    """Agent that crawls screens to build a navigation graph.

    Safety limits:
    - Max depth: 8
    - Max screens: 50 per session
    - Never sends credentials
    - Skips hidden input fields
    """

    def __init__(self, graph: TrustGraph = None, max_depth: int = 8, max_screens: int = 50):
        self.graph = graph or get_trust_graph()
        self.max_depth = max_depth
        self.max_screens = max_screens
        self.screens_visited = 0
        self.visited_hashes = set()
        self.current_depth = 0
        self.navigation_stack = []  # Stack of (panel_id, pf_keys_tried)
        self.entry_point_id = None

    def start_mapping(self, screen_text: str, host: str = None) -> Dict:
        """Start mapping from the current screen.

        Args:
            screen_text: Initial screen content
            host: Optional host identifier

        Returns:
            Initial state dict
        """
        self.screens_visited = 0
        self.visited_hashes = set()
        self.current_depth = 0
        self.navigation_stack = []

        # Create entry point
        entry_label = host or "ENTRY"
        self.entry_point_id = self.graph.add_node(
            "EntryPoint",
            entry_label,
            properties={"host": host},
            evidence={"type": "agent_start", "timestamp": datetime.now().isoformat()}
        )

        # Process initial screen
        result = self._process_screen(screen_text, None, None)

        # Link entry to first panel
        if result.get("panel_id"):
            self.graph.add_edge("TRANSITIONS_TO", self.entry_point_id, result["panel_id"])
            self.navigation_stack.append((result["panel_id"], []))

        return {
            "status": "started",
            "entry_point_id": self.entry_point_id,
            "panel_id": result.get("panel_id"),
            "panel_type": result.get("panel_type"),
            "screens_visited": self.screens_visited
        }

    def process_screen(self, screen_text: str, action_taken: Dict = None) -> Dict:
        """Process a screen and decide next action.

        Args:
            screen_text: Current screen content
            action_taken: What action was taken to get here

        Returns:
            Dict with next action to take
        """
        if self.screens_visited >= self.max_screens:
            return {"action": "stop", "reason": "max_screens_reached"}

        if self.current_depth >= self.max_depth:
            return {"action": "backtrack", "pf_key": 3}

        # Check if we've seen this screen
        screen_hash = hashlib.md5(screen_text.encode()).hexdigest()[:16]
        if screen_hash in self.visited_hashes:
            return self._decide_next_action()

        self.visited_hashes.add(screen_hash)

        # Get previous panel ID
        prev_panel_id = None
        if self.navigation_stack:
            prev_panel_id = self.navigation_stack[-1][0]

        # Process the screen
        result = self._process_screen(screen_text, prev_panel_id, action_taken)

        # Update navigation stack
        if result.get("panel_id") and result["panel_id"] != prev_panel_id:
            self.navigation_stack.append((result["panel_id"], []))
            self.current_depth += 1

        return self._decide_next_action()

    def _process_screen(self, screen_text: str, prev_panel_id: str,
                        action_taken: Dict) -> Dict:
        """Internal screen processing."""
        self.screens_visited += 1

        stats = update_graph_from_screen(
            self.graph,
            screen_text,
            prev_panel_id,
            action_taken
        )

        panel_info = classify_panel(screen_text)
        stats["panel_type"] = panel_info.get("panel_type")

        return stats

    def _decide_next_action(self) -> Dict:
        """Decide what action to take next."""
        if not self.navigation_stack:
            return {"action": "stop", "reason": "navigation_complete"}

        current_panel_id, pf_keys_tried = self.navigation_stack[-1]

        # Standard exploration PF keys
        explore_keys = [1, 2, 4, 5, 6, 7, 8]  # Skip PF3 (back)

        for key in explore_keys:
            if key not in pf_keys_tried:
                pf_keys_tried.append(key)
                return {"action": "send_pf_key", "key": key}

        # All keys tried at this level, backtrack
        self.navigation_stack.pop()
        self.current_depth -= 1

        if self.navigation_stack:
            return {"action": "send_pf_key", "key": 3}  # PF3 to go back
        else:
            return {"action": "stop", "reason": "exploration_complete"}

    def get_stats(self) -> Dict:
        """Get mapping statistics."""
        return {
            "screens_visited": self.screens_visited,
            "unique_screens": len(self.visited_hashes),
            "current_depth": self.current_depth,
            "stack_depth": len(self.navigation_stack),
            "graph_stats": self.graph.get_stats()
        }


# =============================================================================
# Batch Trust Agent
# =============================================================================

class BatchTrustAgent:
    """Agent that parses JCL and SYSOUT to build execution chain graphs."""

    def __init__(self, graph: TrustGraph = None):
        self.graph = graph or get_trust_graph()
        self.jobs_processed = 0
        self.sysouts_processed = 0

    def ingest_jcl(self, jcl_text: str, source: str = None) -> Dict:
        """Ingest JCL and update the graph.

        Args:
            jcl_text: JCL content
            source: Source identifier (filename, dataset, etc.)

        Returns:
            Processing result
        """
        evidence = {
            "type": "jcl",
            "source": source,
            "timestamp": datetime.now().isoformat()
        }

        parsed = parse_jcl(jcl_text)
        if parsed.get("parse_errors"):
            return {"success": False, "errors": parsed["parse_errors"]}

        stats = update_graph_from_jcl(self.graph, parsed, evidence)
        self.jobs_processed += 1

        return {
            "success": True,
            "jobname": parsed.get("jobname"),
            "steps": len(parsed.get("steps", [])),
            "programs": parsed.get("programs_referenced", []),
            "datasets": parsed.get("datasets_referenced", []),
            "loadlibs": parsed.get("loadlibs", []),
            "graph_updates": stats
        }

    def ingest_sysout(self, sysout_text: str, source: str = None) -> Dict:
        """Ingest SYSOUT and update the graph.

        Args:
            sysout_text: SYSOUT content
            source: Source identifier

        Returns:
            Processing result
        """
        evidence = {
            "type": "sysout",
            "source": source,
            "timestamp": datetime.now().isoformat()
        }

        parsed = parse_sysout(sysout_text)
        stats = update_graph_from_sysout(self.graph, parsed, evidence)
        self.sysouts_processed += 1

        return {
            "success": True,
            "jobname": parsed.get("jobname"),
            "jobid": parsed.get("jobid"),
            "overall_rc": parsed.get("overall_rc"),
            "overall_abend": parsed.get("overall_abend"),
            "datasets_allocated": parsed.get("datasets_allocated", []),
            "graph_updates": stats
        }

    def get_stats(self) -> Dict:
        """Get agent statistics."""
        return {
            "jobs_processed": self.jobs_processed,
            "sysouts_processed": self.sysouts_processed,
            "graph_stats": self.graph.get_stats()
        }


# =============================================================================
# CICS Relationship Agent
# =============================================================================

class CICSRelationshipAgent:
    """Agent that extracts CICS transaction/program/region relationships."""

    def __init__(self, graph: TrustGraph = None):
        self.graph = graph or get_trust_graph()
        self.screens_processed = 0

    def process_cics_screen(self, screen_text: str) -> Dict:
        """Process a CICS screen and extract relationships.

        Args:
            screen_text: CICS screen content

        Returns:
            Processing result
        """
        if not CICS_HELPER:
            return {"success": False, "error": "CICS helper not available"}

        if not CICS_HELPER.detect_cics_screen(screen_text):
            return {"success": False, "error": "Not a CICS screen"}

        evidence = {
            "type": "cics_screen",
            "timestamp": datetime.now().isoformat()
        }

        result = {
            "success": True,
            "transactions": [],
            "programs": [],
            "region": None,
            "graph_updates": {"nodes_added": 0, "edges_added": 0}
        }

        # Extract APPLID (region)
        applid_match = APPLID_PATTERN.search(screen_text)
        region_id = None
        if applid_match:
            region_name = applid_match.group(1)
            region_id = self.graph.add_node("CICSRegion", region_name, evidence=evidence)
            result["region"] = region_name
            result["graph_updates"]["nodes_added"] += 1

        # Parse CEMT output
        cemt_resources = CICS_HELPER.parse_cemt_output(screen_text)
        for resource in cemt_resources:
            if resource["type"] == "TRANSACTION":
                trans_id = self.graph.add_node(
                    "Transaction",
                    resource["name"],
                    properties={"status": resource.get("status")},
                    evidence=evidence
                )
                result["transactions"].append(resource["name"])
                result["graph_updates"]["nodes_added"] += 1

                if region_id:
                    self.graph.add_edge("RUNS_IN", trans_id, region_id, evidence=evidence)
                    result["graph_updates"]["edges_added"] += 1

            elif resource["type"] == "PROGRAM":
                pgm_id = self.graph.add_node(
                    "Program",
                    resource["name"],
                    properties={"status": resource.get("status")},
                    evidence=evidence
                )
                result["programs"].append(resource["name"])
                result["graph_updates"]["nodes_added"] += 1

        # Parse CEDF output for transaction->program bindings
        cedf_info = CICS_HELPER.parse_cedf_screen(screen_text)
        if cedf_info.get("transaction") and cedf_info.get("program"):
            trans_id = self.graph.add_node("Transaction", cedf_info["transaction"], evidence=evidence)
            pgm_id = self.graph.add_node("Program", cedf_info["program"], evidence=evidence)
            self.graph.add_edge("INVOKES", trans_id, pgm_id, evidence=evidence, confidence=0.9)
            result["graph_updates"]["edges_added"] += 1

        self.screens_processed += 1
        return result

    def get_stats(self) -> Dict:
        """Get agent statistics."""
        return {
            "screens_processed": self.screens_processed,
            "graph_stats": self.graph.get_stats()
        }
