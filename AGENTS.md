# Repository Guidelines

## Project Structure & Module Organization

This repository combines a local AI development harness with generated product code. Treat `.ai/`, `presets/`, and harness configuration files as orchestration assets, not product source. Product/application code belongs under `src/`; tests belong under `tests/`. Harness run artifacts are written to `.ai/runs/<feature>/`, feature stage outputs to `.ai/features/<feature>/`, long-term history to `.ai/history/`, and generated documents to `.ai/docs/`.

Do not create root-level product files unless the user explicitly asks for a root entry point or the existing project convention requires it.

## Build, Test, and Development Commands

- `python .ai\harness_fast.py doctor`: check fast-pipeline presets, provider availability, and schedule preview.
- `python .ai\harness_standard.py run "request" --feature feature-name --yes --defaults`: run the normal spec/develop/review/fix/verify workflow.
- `python .ai\harness.py run "request" --feature feature-name --yes --defaults`: run the full workflow, including documentation and project-contract candidate extraction.
- `python -m py_compile .ai\harness.py .ai\harness_fast.py .ai\harness_standard.py .ai\templates\docx_helper.py`: validate harness Python syntax.
- `python .ai\pc_review.py`: review pending Project Contract candidates.

Project-specific build or test commands should be configured in `.ai/harness.config.json` under `verification.commands`.

## Coding Style & Naming Conventions

Keep changes scoped to the active feature. Prefer existing local patterns over new abstractions. Use descriptive feature slugs such as `settings-tooltips` or `make-start-batfile`. Python harness code uses 4-space indentation, typed function signatures where practical, and JSON files with two-space indentation. Keep generated stage outputs named exactly as required by the harness.

## Testing Guidelines

Run the configured harness verification before considering a feature complete. Add or update tests under `tests/`; do not place tests under `src/`. Do not delete or disable existing tests to make a run pass. Record commands and results in the stage output and result JSON.

## Commit & Pull Request Guidelines

The harness owns Git commits. Agents must not run `git commit`, `git commit --amend`, `git reset`, `git checkout`, `git rebase`, or `git push`. Harness-managed commit messages follow:

```text
[feature][YYYYMMDD-hhmmss][stage]
```

For PRs, include the feature name, changed files, verification results, unresolved risks, and screenshots or logs when UI or runtime behavior changed.

## Agent-Specific Instructions

Read `.ai/project_contract.md` before changing files. Preserve harness files unless the task is explicitly about the harness. Keep `.ai/runs/` and `.ai/features/` artifacts consistent with the active stage.
