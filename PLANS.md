# PLANS.md — Execution protocol for repo-wide documentation

## Step 0 — Scan (no writing yet)

- Identify stack: runtime, framework, build tool, language
- Identify entrypoints and main modules
- Identify scripts/commands and package manager
- Identify env vars usage (names only)
- Identify conventions and boundaries (where changes should happen)

## Step 1 — Outline (propose before writing)

Propose:

- STRUCTURE.md outline (headings + bullet notes)
- TOOLS.md outline (headings + bullet notes)
  List any uncertainties as explicit assumptions.

## Step 2 — Write files

Write final contents for:

- STRUCTURE.md
- TOOLS.md

## Step 3 — Self-check

- Ensure no invented files/scripts
- Ensure commands match repo scripts
- Ensure upgrade/migration rules are included (replace, don’t wrap; no dead code)
- Ensure output is ready to commit
