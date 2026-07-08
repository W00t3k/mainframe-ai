# Memory Architecture

Mainframe AI should separate immediate working context, retrievable knowledge, learned behavior, and repeatable actions. Mixing these concepts leads to models that memorize the wrong thing, miss current screen state, or answer with Unix/Linux assumptions.

## Short-Term Memory

Short-term memory is the current working context. It changes quickly and should be treated as session state, not long-term knowledge.

Examples:

- Current terminal output.
- Current 3270 screen.
- Active VTAM menu or TSO panel.
- Current ISPF dataset member.
- Recent JES job output or SYSOUT being inspected.
- The user's current question and the assistant's recent reasoning.

Security value: short-term memory tells BigIron.ai what is happening now. A RACF error, JES message, APF library reference, or TSO prompt may only be meaningful in the context of the current screen and preceding command.

## Long-Term Memory

Long-term memory is retrieval material. It should live in RAG, vector search, local indexes, transcripts, and private document stores.

Examples:

- RAG snippets from private Redbooks.
- Lab transcripts and walkthrough notes.
- JCL examples collected from local labs.
- RACF, TSO, ISPF, VTAM, CICS, JES, APF, and SMF reference notes.
- Sanitized assessment observations.
- Local SYSOUT and screen captures used as evidence.

Security value: long-term memory provides facts and examples that the model can cite or reason from. It is the right place for private Redbooks and copyrighted IBM documentation because those sources should not be committed to the repo or pasted into training data.

## Fine-Tuning

Fine-tuning should teach behavior and instincts, not store facts.

Good fine-tuning targets:

- Prefer RACF and dataset profiles over `/etc/passwd` assumptions.
- Treat JES as deferred execution, not just a job runner.
- Recognize APF authorization as a mainframe trust boundary, not `sudo`.
- Explain findings using concept, security impact, assessment angle, and lab-safe example.
- Ask for SMF, SYSOUT, spool, RACF, and started task evidence before making claims.

Bad fine-tuning targets:

- Memorizing Redbook passages.
- Storing private client facts.
- Encoding site-specific credentials, dataset names, or hostnames.
- Replacing RAG with stale model memory.

## Skills And Tools

Skills and tools are repeatable actions that the app or Codex can perform. They should be explicit, testable, and scoped.

Examples:

- Validate training JSONL.
- Check Apple Silicon readiness.
- Query Ollama for available local models.
- Retrieve RAG snippets from a private corpus.
- Summarize current TN3270 screen context.
- Explain a JCL finding.
- Map a writable PROCLIB or APF library to a trust boundary.

Security value: skills turn common assessment actions into repeatable workflows without hiding important assumptions.

## BigIron.ai Example Flow

1. Short-term memory contains the current 3270 screen showing an ISPF panel and the latest terminal output.
2. A RAG query retrieves private notes about dataset profiles, PROCLIB handling, JES spool, and SMF evidence.
3. The model behavior, shaped by SFT examples, avoids generic Linux answers and reasons in RACF, JES, JCL, TSO, ISPF, datasets, APF, VTAM, CICS, SMF, and started task identity.
4. A tool validates any generated JSONL examples before they are committed.

The goal is not to make one memory layer do every job. Current screen state belongs in short-term memory, private reference material belongs in RAG, behavioral preference belongs in fine-tuning, and repeatable actions belong in skills or tools.
