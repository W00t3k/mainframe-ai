# BigIron-AI Training Fixes

Track knowledge gaps and issues for the next training run.

## Pending Fixes

| Issue | Status | File Added |
|-------|--------|------------|
| OS/2 confused with z/OS, incorrectly associated with RACF | Ready | `mainframe_history_architecture.jsonl` |
| JES2 not explained properly | Ready | `mainframe_history_architecture.jsonl` |
| PDS member enumeration for red team missing | Ready | `mainframe_recon_defense.jsonl` |
| PDS member content reading missing | Ready | `mainframe_recon_defense.jsonl` |
| ISPF 3.4 reconnaissance guide missing | Ready | `mainframe_recon_defense.jsonl` |
| PDS sensitive data search missing | Ready | `mainframe_recon_defense.jsonl` |
| Complete PDS security methodology missing | Ready | `mainframe_recon_defense.jsonl` |
| APF exploitation wrong (fake commands) | Ready | `mainframe_recon_defense.jsonl` |
| RACF user enumeration wrong commands | Ready | `mainframe_recon_defense.jsonl` |
| Console commands fabricated | Ready | `mainframe_recon_defense.jsonl` |
| Started task security analysis wrong | Ready | `mainframe_recon_defense.jsonl` |
| SMF record types incorrect | Ready | `mainframe_recon_defense.jsonl` |
| VSAM security check nonsense | Ready | `mainframe_recon_defense.jsonl` |
| Privilege escalation paths fabricated | Ready | `mainframe_recon_defense.jsonl` |
| SDSF confused with ISPF functions | Ready | `mainframe_recon_defense.jsonl` |
| TSO security commands wrong | Ready | `mainframe_recon_defense.jsonl` |
| FTP reconnaissance not mainframe-specific | Ready | `mainframe_recon_defense.jsonl` |

## How to Add a Fix

1. Add JSONL example to `data/training/examples/`
2. Log it here with status "Ready"
3. When batch is 10-20 fixes, retrain:
   ```bash
   ./scripts/training/build_bigiron_ai.sh
   ```

## Completed (included in current model)

None yet - this is v1.

## Notes

- Current model: bigiron-ai (15 epochs, 6,210 samples)
- Last trained: 2026-07-13
- Fixes batched: 17 total (ready for retrain)
- mainframe_recon_defense.jsonl: 7 → 22 examples
