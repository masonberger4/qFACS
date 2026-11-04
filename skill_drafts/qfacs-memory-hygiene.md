---
name: qfacs-memory-hygiene
description: Use at the start and end of any thread in the Quantbrite Automation (qFACS) project to read and update the memory folder correctly.
---
0. Check threads.md for active threads.
1. Read the memory index, then only the topic file you need in /mnt/project-files/memory/ (grep by keyword).
2. Before asking the owner a question, grep decisions.md; their answers are final.
3. Top-level files are read-only unless you are a writer in ACL.json. Your pad is scratch/<your-slug>/. For a top-level change use `memsave.py propose FILE --agent ... --reason ... --link ...` (text on stdin). Change files ONLY with `python3 /mnt/project-files/memory/tools/memsave.py`: hash, draft, save with --base (exit 3 = STALE: re-pull, redraft, retry; never force). Always say what conversation/incident caused the change.
4. Save what a new thread would re-ask: writers use `append`; others write scratch/<slug>/notes.md AND `propose` the same text. Use UTC date and who decided. Keep the index short; no secrets.
5. Work over 30 min: check in and commit+push at least every 30 min.
6. When finishing, list in your final reply any learned fact not in memory (one line each); the coordinator proposes them.
