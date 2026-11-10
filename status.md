# Live status
Short, current. Overwrite freely (by a writer). What is in flight, what is blocked, what needs the owner.

2026-11-06 (dreamer):
- Done: phase 1 setup template + validator (PR #2), phase 2 engine from FlowJo exports (PR #2, Excel v1 Plate 1 regression to 0.1%), confirmed F/P (PR #3), phase 3 .fcs + .wsp reader with FlowJo-style gMFI and auto bead peaks (PR #5). PRs #1-#5 all merged into `main`. Test kit: /mnt/project-files/test_run/qFACS_test_run.zip (Windows .bat launchers untested). Cloud runs: Mase uploads setup + data to the build thread and Claude runs it.
- Waiting on Mase: edited setup workbook (test_run/to_edit/), then .fcs files for a real run (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBJfoD2hGW6jMo42kwoAXNrM). For better auto gating: one gated .wsp + .fcs per common cell line, a live/dead-only or heat-killed control, PE-only and reporter-only controls.
- Next build work: phase 4 (gate library per cell line, Live cutoff, unmixing).
- Needs Mase: confirm "AWAITING" analysis defaults in decisions.md; approve memory proposals.
