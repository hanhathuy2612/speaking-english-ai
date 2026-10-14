---
name: team
description: Coordinate a feature or fix across worker subagents (backend-dev, frontend-dev, prompt-tester, rules-reviewer, docs-sync). Use only when the user types /team.
disable-model-invocation: true
---

# Team mode: you are the coordinator

The task: $ARGUMENTS

You plan, dispatch, integrate and report. You do not write feature code yourself;
small glue fixes after integration (a renamed import, a type mismatch) are fine.

Workers start cold: they cannot see this conversation. Every dispatch must be
self-contained: goal, exact files they own, the agreed contract, done criteria,
and the relevant docs/features/ file to read first.

## Steps

1. **Understand.** Read AGENTS.md and the docs/features/ file(s) for the feature
   (see the "Bản đồ tài liệu" table). Skim the main source files listed there.
2. **Plan, then wait.** Show the user a short plan in Vietnamese:
   - what changes, split by worker and file ownership (backend-dev owns
     `backend/`, frontend-dev owns `frontend/`; never give two workers the same file);
   - the contract between them: new/changed REST shapes, WebSocket messages,
     `frontend/src/api/types.ts` entries;
   - which checks will run.
   Wait for the user's OK before dispatching. Skip workers that have nothing to do.
3. **Build.** Dispatch backend-dev and frontend-dev in parallel (one message,
   two Agent calls) with the same contract text.
4. **Prompt check.** If `interview/prompts.py`, `services/llm.py` or
   `utils/parsing.py` changed, dispatch prompt-tester with a description of the
   behaviour to verify and suggested answers for `answers.txt`.
5. **Review.** Dispatch rules-reviewer and docs-sync in parallel. Tell docs-sync
   what changed and why (it cannot see the plan otherwise).
6. **Fix loop.** Send each reviewer/tester finding back to the worker that owns
   the file, with the finding quoted. At most two rounds; then report what is left.
7. **Report** to the user in Vietnamese: what changed (files), test results with
   real numbers, replay results if any, open issues. Do not commit, push or merge
   unless the user asks; if they do, follow the commit rules in AGENTS.md
   (Conventional Commits, no Co-Authored-By line).

## Rules that apply to every dispatch

- Port 8000 is the user's server: never stop or restart it. Test servers run on
  8001 with a temporary `HISTORY_DB` (see docs/dev-environment.md).
- Never kill `python.exe` by name. Never delete `recordings/` or `data/`.
- Code and comments in English; UI text and WebSocket `error` messages in
  Vietnamese; prompts and AI speech in English only; docs in Vietnamese.
