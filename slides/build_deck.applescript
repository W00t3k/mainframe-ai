set baseDir to POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/" as alias
set logoFile to POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/ibm-old.png" as alias
set outFile to POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/AI-Powered_zOS_Operations.pptx"

set abstractText to "Mainframe operating systems run critical financial, government, and transportation infrastructure, yet most offensive security methodologies approach them using assumptions inherited from Unix, Windows, and modern enterprise platforms. These assumptions frequently fail on mainframe operating systems, leading to assessments that miss the real attack surface.\n\nThis talk examines these systems from an attacker’s perspective, focusing on how exposure, privilege, and segmentation actually work in environments built for batch processing, transaction processing, and long-running workloads. We explore why concepts such as shells, ports, and traditional lateral movement do not map cleanly, and where attackers instead operate: transaction managers, security definitions, and system control boundaries.\n\nUsing real TN3270 terminal interactions and practical examples, the talk presents a repeatable offensive methodology for mapping and assessing mainframe environments. The session concludes with the release of an open-source tool, AI-Powered z/OS Operations, that assists with TN3270 environment discovery and screen interpretation during testing.\n\nNo prior mainframe experience is required, but the content is designed for experienced offensive practitioners."

set slideData to {¬
    {"Home", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/01-root.png" as alias, ¬
        "- Local-first AI assistant for z/OS operations" & return & ¬
        "- TN3270 terminal + BIRP v2 integration" & return & ¬
        "- Launch points for Abstract Models, Tutor, Walkthrough"}, ¬
    {"Walkthrough", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/02-walkthrough.png" as alias, ¬
        "- Autonomous demo that connects and navigates VTAM -> TSO -> ISPF" & return & ¬
        "- Tracks the 5 assessment questions (Q1-Q5)" & return & ¬
        "- Live terminal screen with narrated steps"}, ¬
    {"Terminal", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/03-terminal.png" as alias, ¬
        "- TN3270 terminal with host:port connect" & return & ¬
        "- Keyboard support: Enter, Tab, PF keys, Clear" & return & ¬
        "- Live screen updates for interactive testing"}, ¬
    {"AI Chat", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/04-chat.png" as alias, ¬
        "- Multi-panel view: Chat, Terminal, RAG" & return & ¬
        "- Agent + model status (Ollama, TN3270, RAG)" & return & ¬
        "- Quick commands and connected sources"}, ¬
    {"Red Team Tutor", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/05-tutor.png" as alias, ¬
        "- Module-driven training (Session Stack, Batch, Dataset Trust)" & return & ¬
        "- Persona selection: Mentor, Operator, Red Teamer, Forensics" & return & ¬
        "- Embedded TN3270 terminal for guided steps"}, ¬
    {"Trust Graph", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/06-graph.png" as alias, ¬
        "- Graph of panels, jobs, programs, datasets, and edges" & return & ¬
        "- Queries for paths and shared data" & return & ¬
        "- Ingest from JCL/SYSOUT/screens; export DOT"}, ¬
    {"RAG Manager", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/07-rag.png" as alias, ¬
        "- Built-in mainframe sources (ABEND, JCL, COBOL)" & return & ¬
        "- Upload PDFs and manage documents" & return & ¬
        "- Test queries and view stats"}, ¬
    {"Recon", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/08-recon.png" as alias, ¬
        "- Methodology: core problem and broken assumptions" & return & ¬
        "- Five assessment questions for z/OS" & return & ¬
        "- Emphasis on control planes and identity binding"}, ¬
    {"Scanner", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/09-scanner.png" as alias, ¬
        "- Scan networks for TN3270 services" & return & ¬
        "- Target host/IP/CIDR + port list" & return & ¬
        "- Launch to terminal and AI chat"}, ¬
    {"Screencaps", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/10-screencaps.png" as alias, ¬
        "- Saved terminal screens for documentation" & return & ¬
        "- Storage usage and capture list" & return & ¬
        "- View, save, delete per capture"}, ¬
    {"Labs", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/11-labs.png" as alias, ¬
        "- Deterministic labs without a live mainframe" & return & ¬
        "- Session Stack and Batch Execution walkthroughs" & return & ¬
        "- Step-by-step JCL review"}, ¬
    {"Architecture", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/12-architecture.png" as alias, ¬
        "- System architecture and request flow" & return & ¬
        "- Web UI, API layer, RAG engine, TN3270 pipeline" & return & ¬
        "- Local LLM + storage integrations"}, ¬
    {"Abstract Models", POSIX file "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/slides/screenshots/13-abstract_models.png" as alias, ¬
        "- Platform thesis and mental models" & return & ¬
        "- Click TN3270 regions to map to models" & return & ¬
        "- Persona + module navigation guidance"} ¬
}

set ibmBlue to {3855, 25186, 65278}
set darkGray to {13107, 13107, 13107}

tell application "Keynote"
    activate
    set doc to make new document
    tell doc
        -- Title slide
        set s1 to make new slide with properties {base layout:slide layout "Blank"}
        tell s1
            set t1 to make new text item with properties {object text:"AI-Powered z/OS Operations", position:{60, 80}, width:1800, height:80}
            set font of object text of t1 to "Helvetica Neue"
            set size of object text of t1 to 54
            set color of object text of t1 to ibmBlue
            set t2 to make new text item with properties {object text:"Offensive Methodology for Mainframe Environments", position:{60, 170}, width:1800, height:60}
            set font of object text of t2 to "Helvetica Neue"
            set size of object text of t2 to 28
            set color of object text of t2 to darkGray
            make new image with properties {file:logoFile, position:{1600, 40}, width:240, height:70}
        end tell

        -- Abstract slide
        set s2 to make new slide with properties {base layout:slide layout "Blank"}
        tell s2
            set t3 to make new text item with properties {object text:"Abstract", position:{60, 40}, width:1800, height:60}
            set font of object text of t3 to "Helvetica Neue"
            set size of object text of t3 to 40
            set color of object text of t3 to ibmBlue
            set t4 to make new text item with properties {object text:abstractText, position:{60, 120}, width:1800, height:860}
            set font of object text of t4 to "Helvetica Neue"
            set size of object text of t4 to 20
            set color of object text of t4 to darkGray
            make new image with properties {file:logoFile, position:{1600, 30}, width:240, height:70}
        end tell

        -- Component slides
        repeat with sd in slideData
            set slideTitle to item 1 of sd
            set slideImage to item 2 of sd
            set s to make new slide with properties {base layout:slide layout "Blank"}
            tell s
                set tt to make new text item with properties {object text:slideTitle, position:{60, 30}, width:1500, height:60}
                set font of object text of tt to "Helvetica Neue"
                set size of object text of tt to 36
                set color of object text of tt to ibmBlue
                make new image with properties {file:logoFile, position:{1600, 20}, width:240, height:70}
                make new image with properties {file:slideImage, position:{60, 110}, width:1200, height:900}
                set tb to make new text item with properties {object text: (item 3 of sd), position:{1300, 110}, width:560, height:900}
                set font of object text of tb to "Helvetica Neue"
                set size of object text of tb to 20
                set color of object text of tb to darkGray
            end tell
        end repeat
    end tell

    export doc to outFile as Microsoft PowerPoint
end tell
