<!-- proposal by Review prior qFACS workbook work at 2026-11-04 22:21:39Z; target: data.md; reason: record prior-work files and input formats; link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJmHYQJezAabrQ4aNv6qb5f; PR https://github.com/masonberger4/qFACS/pull/1; status: merged v27 -->
## Prior work and input formats (2026-11-04, thread "Review prior qFACS workbook work")
- /mnt/project-files/prior_work/excel_v1/: Excel-only workbook from an earlier session (build_qfacs_xl.py, qFACS_Import.pq, master template, Plate1 example). Also in repo legacy/excel_v1/ (PR #1 into new `main`; code base branch is `main`, memory stays on `memory`).
- That workbook reads FlowJo table exports (.xls), not .fcs: "<PlateID> <CellLine>.xls" per cell line, PE stat "Geometric Mean (B5 (575)-A)", bead export name contains "bead" with gates Low / Med Low / Med High / High.
- BD A8 guide (both PDFs identical, 498 pp, scanned, no text layer; read pages as images). Export chapter p.317-327: FACSChorus exports FCS, statistics CSV, CEF, CVW; exported FCS/stats reflect the unmixing matrix assigned at export time. Plate loader p.300.
- Bead lot in workbook: 42618 (474 / 5359 / 23843 / 62336 PE per bead), expired 2022-10-31.
- Exp2281 setup: 21 cell lines, 11 plates (2 lines per plate, rows A-D / E-H), CD58, B7H3, DLL3, mIgG1 isotype; top 50 µg/mL final, 1.8x, 11 points, col 12 = no antibody; cells PFA-fixed.
