<!-- proposal by Review prior qFACS workbook work at 2026-11-05 21:00:32Z; target: decisions.md; reason: Mase's inline edits to build plan; link: https://claude.ai/artifact/MKhhyuQpTo8xxKecP1LEhv; status: open -->
## Build plan edits (2026-11-05, Mase, inline in plan doc)
- Users: Mase and other lab members (plural).
- Never hard-code reagent values: F/P, valency, concentration, catalog #, lot #, PE bead lot values all user-entered.
- Engine runs locally until confirmed working, then moves to a locally hosted web UI.
- Example .fcs/.wsp/FlowJo export: Mase will add to the thread; FlowJo export sample to be uploaded.
- Single-stain controls (PE-only, reporter-only) will come as .fcs files.
- Fixation head-to-head: to be tested in the future.
- Isotype: add a QC flag checking the isotype run matches (host/isotype) the antibodies tested on that cell line.
