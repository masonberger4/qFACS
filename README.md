# Project memory folder

Layout (this folder, in the project's shared files):
- decisions.md owner answers + standing rules (date, who decided). Check before asking the owner.
- results.md, data.md, ops.md, lessons.md: topic files. status.md live status. threads.md thread registry.
- skill_drafts/ draft skills for the owner to upload (threads cannot install skills).
- proposals/ requested changes and dream reports. scratch/<slug>/ free per-agent pads (git-ignored).
- INDEX.md approved copy of the platform memory index. CHANGELOG.md auto-written, one row per version.

The platform memory (MEMORY.md) is a short index (<3 KB): status, standing rules, pointers here.

## How threads use it
1. Read the index, then only the topic file you need (grep by keyword).
2. Only writers change top-level files; everyone else uses scratch/ or `propose`.
3. Detail goes in topic files, not the index. Never store secrets.
4. Stale long sections: summarize in place with a date; don't delete decisions.

## Versioning and safe saves (required for every edit)
All edits go through `tools/memsave.py` (this folder is a git repo; CHANGELOG.md has who/when/why/link/hash).
1. `H=$(python3 tools/memsave.py hash FILE)` and read FILE.
2. Draft the edit in a scratch file (or text for append).
3. `python3 tools/memsave.py save FILE --base $H --draft DRAFT --agent "<name>" --reason "why" --link "msg/thread/PR"` (or `append ...` with text on stdin). If FILE changed meanwhile it exits 3 (STALE): re-pull, redraft, new hash, retry. Never force.
4. History: `memsave.py log [FILE]`; `show FILE v3`; `rollback FILE v3 --agent ... --reason ...` (restores as a NEW version).

## Permissions
ACL.json "writers" may edit top-level files (refusal = DENIED, exit 4). Non-writers:
- own pad: `scratch/<slug>/` (slug = thread name lowercased, non-alphanumerics -> "-").
- top-level change: `echo "text" | python3 tools/memsave.py propose decisions.md --agent "<you>" --reason "why" --link "..."` -> proposals/<slug>__decisions.md; a writer reviews and merges with `save`.
- `memsave.py verify` lists files edited outside the tool (exit 5).
Limits: identity is self-declared; shared mounts ignore chmod; the platform index tool can't be restricted, so a rule plus the drift check covers it.

## GitHub store and index drift
- Approved store: branch `memory` (ruleset: require PR, block force push, restrict deletions). `memsave.py sync` fast-forwards the folder (IN SYNC / AHEAD / DIVERGED).
- Non-writers never push to `memory`: branch from it, push files, open a PR into `memory`; only the owner merges.
- Index drift: coordinator saves the live index text to a file and runs `memsave.py indexcheck FILE`; exit 7 = restore live index to INDEX.md.
