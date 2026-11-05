# Memory CHANGELOG

One row per version. Roll back with `tools/memsave.py rollback FILE vN ...` (creates a new version; nothing is erased).

| version | when (UTC) | who | file | action | reason | link | hash before -> after |
|---|---|---|---|---|---|---|---|
| v1 | 2026-11-04 22:06:20Z | coordinator | decisions.md | append | initial setup | thread: Set up project memory system | 49a900a063 -> 41b94b7893 |
| v2 | 2026-11-04 22:06:34Z | coordinator | decisions.md | edit | initial setup: fill Active Rules Digest | thread: Set up project memory system | 41b94b7893 -> 84adc24caf |
| v3 | 2026-11-04 22:06:36Z | coordinator | threads.md | edit | initial setup: register thread | thread: Set up project memory system | c4c602bd5c -> 0f460a8c62 |
| v4 | 2026-11-04 22:06:37Z | coordinator | data.md | edit | initial setup: list known inputs | thread: Set up project memory system | cb8ea43645 -> f72f09aab6 |
| v5 | 2026-11-04 22:06:56Z | coordinator | decisions.md | edit | Mase: no project-specific standing rules yet | cmsg_01Y3oxsYABfATcqbm4kp4uVBGfpWMCpEixpKGWfWmHHq6w | 84adc24caf -> 03519afde8 |
| v6 | 2026-11-04 22:06:58Z | coordinator | INDEX.md | edit | Mase: no project-specific standing rules yet | cmsg_01Y3oxsYABfATcqbm4kp4uVBGfpWMCpEixpKGWfWmHHq6w | cf3ddcc8ef -> 20222e8ff2 |
| v7 | 2026-11-04 22:07:47Z | coordinator | threads.md | edit | register curator and dreaming routine | thread: Set up project memory system | 0f460a8c62 -> 9e2d021525 |
| v8 | 2026-11-04 22:07:50Z | coordinator | status.md | edit | setup status | thread: Set up project memory system | fe74fe510c -> c143b24acd |
| v9 | 2026-11-04 22:07:58Z | coordinator | INDEX.md | edit | fix dream report path, routine created | thread: Set up project memory system | 20222e8ff2 -> 263c52bc58 |
| v10 | 2026-11-04 22:21:39Z | Review prior qFACS workbook work | proposals/review-prior-qfacs-workbook-work__data.md | proposal | record prior-work files and input formats | thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJmHYQJezAabrQ4aNv6qb5f; PR https://github.com/masonberger4/qFACS/pull/1 | ABSENT -> 8babd9fcb8 |
| v11 | 2026-11-04 22:21:42Z | Review prior qFACS workbook work | proposals/review-prior-qfacs-workbook-work__results.md | proposal | baseline result from prior workbook | thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJmHYQJezAabrQ4aNv6qb5f; PR https://github.com/masonberger4/qFACS/pull/1 | ABSENT -> fd712f3a1f |
| v12 | 2026-11-04 22:22:06Z | Review prior qFACS workbook work | proposals/review-prior-qfacs-workbook-work__INDEX.md | proposal | index pointer to prior work, per coordinator | PR https://github.com/masonberger4/qFACS/pull/1 | ABSENT -> 49c4bc3f5b |
| v13 | 2026-11-04 23:39:49Z | Review prior qFACS workbook work | proposals/review-prior-qfacs-workbook-work__decisions.md | proposal | Mase's answers to scoping questions | msg cmsg_01Y3oxsYABfATcqbm4kp4uVB6cVH9VPUt24hvTMMzC2JN2 | ABSENT -> 7b60c2b410 |
| v14 | 2026-11-04 23:44:48Z | Review prior qFACS workbook work | proposals/review-prior-qfacs-workbook-work__status.md | proposal | build plan drafted | https://claude.ai/artifact/MKhhyuQpTo8xxKecP1LEhv | ABSENT -> 9e3760868c |
| v15 | 2026-11-05 06:09:38Z | dreamer | proposals/dreamer__decisions.md | proposal | dream 2026-11-05 D2: record Claude-recommended analysis defaults as pending owner confirmation | cmsg_01Y3oxsYABfATcqbm4kp4uVBXkS8uJRi9P43NcnSqQJZAs | ABSENT -> 048270d9cf |
| v16 | 2026-11-05 06:09:40Z | dreamer | proposals/dreamer__status.md | proposal | dream 2026-11-05 S1: status.md is stale (ruleset done, new thread work missing) | cmsg_01Y3oxsYABfATcqbm4kp4uVB8VFNGPiKy3YWpwVhojbkzr; cmsg_01Y3oxsYABfATcqbm4kp4uVB3JjV4B5TDCGE3uWcmXrfwf | ABSENT -> e26796ad16 |
| v17 | 2026-11-05 06:09:41Z | dreamer | proposals/dreamer__threads.md | proposal | dream 2026-11-05 T1: registry missing a thread, states stale | list_threads 2026-11-05 | ABSENT -> 07dca4000b |
| v18 | 2026-11-05 06:09:42Z | dreamer | proposals/dreamer__lessons.md | proposal | dream 2026-11-05 L1: three lessons from first day | cmsg_01Y3oxsYABfATcqbm4kp4uVBVp31EWLhjZmHj1EruwJqsz; cmsg_01Y3oxsYABfATcqbm4kp4uVB3JjV4B5TDCGE3uWcmXrfwf; prior review thread | ABSENT -> e165292c5f |
| v19 | 2026-11-05 06:09:42Z | dreamer | proposals/dreamer__data.md | proposal | dream 2026-11-05 A1: fix stale repo line and A8 guide hint | thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJmHYQJezAabrQ4aNv6qb5f | ABSENT -> 1345b9e9ef |
| v20 | 2026-11-05 06:10:07Z | dreamer | proposals/dreamer__dream_2026-11-05.md | proposal | daily dream report 2026-11-05 (first run) | thread cmsg_01Y3oxsYABfATcqbm4kp4uVBGFBWLDVsP3Lv4Cifvhe6GT | ABSENT -> 5c9311a6a0 |
| v21 | 2026-11-05 21:00:33Z | Review prior qFACS workbook work | proposals/review-prior-qfacs-workbook-work__decisions.md | proposal | Mase's inline edits to build plan | https://claude.ai/artifact/MKhhyuQpTo8xxKecP1LEhv | 7b60c2b410 -> 0289341ec3 |
| v22 | 2026-11-05 21:17:54Z | Review prior qFACS workbook work | proposals/review-prior-qfacs-workbook-work__results.md | proposal | phase 2 results and phase 3 feasibility | https://github.com/masonberger4/qFACS/pull/2 | fd712f3a1f -> f1ce6bd4e8 |
| v23 | 2026-11-05 21:25:53Z | qfacs-build-thread | proposals/qfacs-build-thread__decisions.md | proposal | layout + F/P confirmation from Mase | https://github.com/masonberger4/qFACS/pull/3 | ABSENT -> c11a3e137f |
| v24 | 2026-11-05 21:28:01Z | qfacs-build-thread | proposals/qfacs-build-thread__decisions.md | proposal | DLL3 F/P confirmed | https://github.com/masonberger4/qFACS/pull/3 | c11a3e137f -> c158dec94b |
| v25 | 2026-11-05 21:34:45Z | dreamer | proposals/dreamer__status.md | proposal | dream 2026-11-05 S1 (updated: skills now installed) | cmsg_01Y3oxsYABfATcqbm4kp4uVBCNNDfbyv4VzB3eCz6arvfZ | e26796ad16 -> deadfc2658 |
| v26 | 2026-11-05 21:36:42Z | Run memory curator | decisions.md | edit | dream 2026-11-05 D1+D2: build plan edits + proposed defaults (AWAITING Mase) | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | 03519afde8 -> 67034f306a |
| v27 | 2026-11-05 21:36:45Z | Run memory curator | data.md | edit | dream 2026-11-05 D1: prior work and input formats | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | f72f09aab6 -> 2eb11777ec |
| v28 | 2026-11-05 21:36:46Z | Run memory curator | results.md | edit | dream 2026-11-05 D1: phase 2 engine results | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | ead9b3f38a -> 4a35acbf27 |
| v29 | 2026-11-05 21:36:47Z | Run memory curator | status.md | edit | dream 2026-11-05 S1 (+D1 build-plan line) | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | c143b24acd -> d070068e91 |
| v30 | 2026-11-05 21:36:48Z | Run memory curator | threads.md | edit | dream 2026-11-05 T1: registry update | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | 9e2d021525 -> 1d072c545e |
| v31 | 2026-11-05 21:36:49Z | Run memory curator | lessons.md | edit | dream 2026-11-05 L1: three lessons | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | 7e77b12c38 -> 879c3e1279 |
| v32 | 2026-11-05 21:36:58Z | Run memory curator | proposals/review-prior-qfacs-workbook-work__decisions.md | edit | mark proposal merged v26 | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | 0289341ec3 -> 384fb96931 |
| v33 | 2026-11-05 21:37:01Z | Run memory curator | proposals/dreamer__decisions.md | edit | mark proposal merged v26 | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | 048270d9cf -> 788fc44218 |
| v34 | 2026-11-05 21:37:02Z | Run memory curator | proposals/review-prior-qfacs-workbook-work__data.md | edit | mark proposal merged v27 | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | 8babd9fcb8 -> 86d4c92a97 |
| v35 | 2026-11-05 21:37:03Z | Run memory curator | proposals/review-prior-qfacs-workbook-work__results.md | edit | mark proposal merged v28 | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | f1ce6bd4e8 -> 49ec55d1e4 |
| v36 | 2026-11-05 21:37:05Z | Run memory curator | proposals/review-prior-qfacs-workbook-work__status.md | edit | mark proposal merged v29 (folded into S1) | Mase approval cmsg_01Y3oxsYABfATcqbm4kp4uVB91VKDPp4Ne3kzuEh7mmzRz | 9e3760868c -> 59cdf4887b |
