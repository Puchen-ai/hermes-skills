---
name: karpathy-guidelines
description: Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria. Triggers on signals like "scope creep", "tangential refactor", "don't over-engineer", "LLM coding antipatterns", "junior-engineer test", "spec it first", "make it minimal".
license: MIT
---

# Karpathy Guidelines

Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

**Version:** 1.0 (rounds 1-5, 2026-06). See [Version Notes](#version-notes) at the end for the change history.

## Contents

1. [Think Before Coding](#1-think-before-coding)
2. [Simplicity First](#2-simplicity-first)
3. [Surgical Changes](#3-surgical-changes)
4. [Goal-Driven Execution](#4-goal-driven-execution)
5. [Concrete Example: Before / After](#5-concrete-example-before--after)
6. [Edge Cases — When the Rules Bend](#6-edge-cases--when-the-rules-bend)
7. [Troubleshooting — When Guidelines Conflict](#7-troubleshooting--when-guidelines-conflict)
8. [Pre-Submit Validation Checklist](#8-pre-submit-validation-checklist)
9. [Observability — Watching Yourself in Real Time](#9-observability--watching-yourself-in-real-time)
10. [Quick Reference — Guideline Numbering](#quick-reference--guideline-numbering)
11. [Version Notes](#version-notes)

**Companion file:** [references/anti-patterns.md](references/anti-patterns.md) — 10 named anti-patterns (A1-A10) with code examples and fixes.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Concrete Example: Before / After

**Task (from user):** "Fix the off-by-one bug in `process_items`."

### Before — junior-LLM-style diff (violates guidelines 2, 3, 4)

```diff
- def process_items(items):
-     for i in range(len(items)):
-         item = items[i]
-         do_thing(item)
+ def process_items(items, *, dry_run=False, logger=None, max_retries=3):
+     """Process items with retries, logging, and dry-run support."""
+     logger = logger or logging.getLogger(__name__)
+     results = []
+     errors = []
+     for idx, item in enumerate(items):
+         if dry_run:
+             logger.info("skip %s", item)
+             continue
+         for attempt in range(max_retries):
+             try:
+                 do_thing(item, attempt=attempt)
+                 results.append((idx, item, "ok"))
+                 break
+             except Exception as exc:                   # noqa: BLE001
+                 logger.warning("retry %s: %s", attempt, exc)
+                 errors.append((idx, item, str(exc)))
+         else:
+             logger.error("giving up on %s", item)
+     return {"results": results, "errors": errors}
```

**Why it fails:** added 3 unrequested features (`dry_run`, `logger`, `max_retries`); rewrote working loop into retry/state machine; no test was added despite "fix the bug" framing; changed signature; touched unrelated code (imports, type hints, docstring).

### After — Karpathy-aligned diff (honors guidelines 1–4)

```diff
+ def test_process_items_handles_empty_list():
+     assert process_items([]) == []
+
  def process_items(items):
-     for i in range(len(items)):
-         item = items[i]
+     for item in items:
          do_thing(item)
```

**Why it works:** wrote a failing test first (goal-driven); removed the off-by-one by deleting the index variable rather than patching it (simplicity); three-line diff matches the one-line user request (surgical); no new imports, no signature change.

**Lesson:** When the user asks for a fix, the diff should look *boring*. If the diff is exciting, you probably violated simplicity or surgical-change rules.

For a deeper catalog of recurring anti-patterns (speculative configuration, silent scope expansion, format-only diffs, etc.) with fixes for each, see [references/anti-patterns.md](references/anti-patterns.md).

## 6. Edge Cases — When the Rules Bend

The guidelines above describe the default. Real codebases have wrinkles. Handle these explicitly:

- **User explicitly asks for "production-grade" / "enterprise" / "add tests/docs/config":** then over-engineering *is* the task. Do exactly what they asked — but still ask first if any sub-feature is ambiguous (guideline 1).
- **Legacy code is already bloated:** do NOT clean up pre-existing mess in a surgical fix. Mention it as a follow-up: "I noticed X is also broken; want a separate PR?"
- **Greenfield vs. existing-code asymmetry:** in a new file, bias toward simplicity and zero abstraction. In existing code, bias toward matching local style and not touching adjacent code. These pull opposite directions — read the room.
- **"While you're in there..." mid-task requests:** treat each as a separate sub-task. Apply guideline 3 to each independently; do not bundle them into one diff.
- **User is wrong about the bug location:** say so plainly, then propose the actual fix. Do not silently patch where they pointed if you can show it won't help.
- **Security/correctness pressure vs. minimalism:** never strip error handling, validation, or auth to "simplify". If the original code was defensive for a reason, keep it. Simplicity means removing *speculative* code, not *necessary* code.
- **"Make it work" with no spec:** this is the highest-risk case. Do not guess — list 2–3 plausible interpretations and ask. A wrong assumption is more expensive than a 30-second clarification.

## 7. Troubleshooting — When Guidelines Conflict

You will hit situations where two guidelines pull in opposite directions. Use this decision order:

1. **Correctness first.** Never simplify away a real safety property (auth, validation, error handling, transaction boundaries). Simplicity means no *speculative* code, not no *necessary* code.
2. **User's explicit request overrides defaults.** If they asked for tests, config, docs, or abstractions — give them. If they asked for a minimal fix, do not add them.
3. **Surgical beats simple when they conflict.** If existing code is already ugly, resist rewriting it inside an unrelated fix. Match local style even if you'd do it differently.
4. **Goal-driven beats simple when verification is hard.** For risky changes (schema migrations, concurrency, security), add the test even if it inflates the diff. A verified boring diff beats a clever unverified one.
5. **When truly stuck, surface the tradeoff.** Example: "Simplest fix is 3 lines but won't catch the regression you mentioned. Adding a test makes it 15 lines. Which do you prefer?"

**Common failure modes and fixes:**

| Symptom | Likely violation | Fix |
|---|---|---|
| Diff is 5x larger than the request | Guidelines 2 + 3 | Revert, redo with the one-line ask in mind |
| User says "you went too far" | Guideline 3 | Apologize, split into the minimal fix + a separate proposal for the rest |
| Tests pass but behavior is wrong | Guideline 4 | Success criteria were vague — rewrite them and re-verify |
| You're "improving" comments/formatting | Guideline 3 | Stop. Format-only changes need explicit ask |
| Adding abstractions "for future use" | Guideline 2 | Delete them; YAGNI is a hard rule |
| User asks 3 things, you do 1 and ignore 2 | Guideline 1 | Surface all 3, confirm scope before coding |

**When to break the guidelines (rare, and announce it):**
- Production incident: ship the fix first, clean up after. Say "incident response, will simplify in follow-up."
- User explicitly asks you to be thorough for a one-off deliverable.
- The "minimal" change is itself a footgun (e.g., removing a guard would silently corrupt data). Keep the guard, explain why.

## 8. Pre-Submit Validation Checklist

Run this against your diff *before* you declare done. Each item maps to a guideline; the first one that fails is the one you must fix. Don't submit a diff you can't tick all of.

**The hard gates (any fail = stop, do not submit):**
- [ ] Every changed line traces to a user-stated requirement. (G3)
- [ ] The diff is proportional to the request — under ~2x the user's stated ask in lines, unless the ask itself is large. (G2 + G3)
- [ ] New tests fail on the pre-change code and pass on the post-change code. (G4)
- [ ] No new parameters, flags, or env vars without a current caller. (G2 / A1)
- [ ] The user can read the diff in 30 seconds and understand what changed and why.

**The soft gates (any fail = justify in your reply, then submit):**
- [ ] No reformatting, import reordering, or comment edits outside the lines the task requires. (G3 / A4)
- [ ] No "while I'm here" cleanups, even if the adjacent code is ugly. (G3 / A5)
- [ ] Error handling you removed was either redundant or your reply names what you removed and why.
- [ ] If you asked no clarifying questions, your assumptions are stated explicitly in the reply.

**The meta-gate (always check last):**
- [ ] Would a senior engineer, on first read, call this diff "boring"? If not, you probably violated G2 or G3 — re-read sections 2 and 3 before submitting.

For the full anti-pattern catalog (10 named patterns with code examples and fixes), see [references/anti-patterns.md](references/anti-patterns.md) — that file's "Quick Self-Check" section is the deeper version of this checklist.

## 9. Observability — Watching Yourself in Real Time

The guidelines are about *judgment*, not just *output*. A diff can pass the checklist above and still be wrong because the LLM drifted mid-task. Watch for these signals **while you work**, not just at submission.

**While planning (before writing code):**
- Did the task description mention 1 thing, and you have 3 things in your plan? → Stop. List the 3, ask which are in scope. (G1)
- Are you about to add a config flag, retry loop, or abstraction "just in case"? → Stop. YAGNI applies to plans, not just code. (G2)
- Did you skip stating assumptions? → Stop. Write them down before the first line of code.

**While writing code:**
- Are you touching a file the user didn't mention? → Stop. Either justify it now or revert. (G3)
- Is your line count past 2x what the request implied, and you're "not done yet"? → Stop. You're building features, not fixing the request. (G2 + G3)
- Are you about to add a try/except for a path that doesn't raise in the current code? → Stop. (G2 / A8)
- Did you write a test that you haven't actually run? → Stop. A test you didn't run is an assertion you didn't make. (G4)

**While reviewing your own diff before submit:**
- Run `git diff --stat` (or equivalent). If a file you didn't plan to change shows up, investigate. (G3)
- Grep your diff for `try:`, `except`, `def `, new `import`. Each is a candidate for a "did I need this?" check. (G2)
- Re-read the user's original message. Is the diff a literal answer to it, or a creative interpretation? (G1)
- If the diff feels satisfying or clever, that's a warning sign. It should feel boring. (G2 / A10)

**Telemetry you can keep on yourself:**
- **Lines of context you touched vs. lines the user named.** If the ratio is high, the diff is doing more than the ask.
- **Number of new symbols (functions, classes, parameters) introduced.** Zero is often the right answer for a surgical fix.
- **Time from "user finished typing" to "first code written."** If it's near-zero on a non-trivial task, you skipped planning. (G1)
- **Number of clarifying questions you asked.** Zero on an ambiguous task is a red flag, not a flex.

The goal is not to be paranoid — it's to catch the drift *before* the user does. A diff that the user has to push back on has already cost more than a diff you self-rejected and rewrote.

## Quick Reference — Guideline Numbering

The checklist in section 8 and the in-flight signals in section 9 use short codes. They map as follows:

| Code | Guideline | Section |
|---|---|---|
| G1 | Think Before Coding | [1](#1-think-before-coding) |
| G2 | Simplicity First | [2](#2-simplicity-first) |
| G3 | Surgical Changes | [3](#3-surgical-changes) |
| G4 | Goal-Driven Execution | [4](#4-goal-driven-execution) |
| A1-A10 | Anti-patterns (companion file) | [references/anti-patterns.md](references/anti-patterns.md) |

**Cross-references between files:** Anti-patterns A1, A2, A3, A8, A9, A10 violate G2 (Simplicity). A4 and A5 violate G3 (Surgical). A6 violates G4 (Goal-Driven). A7 violates G1 (Think Before Coding). When the body of this file flags one of these, it points at the catalog entry by code.

## Version Notes

**v1.0** (2026-06) — current. Built over five rounds:

- **Round 1:** Tightened triggers in the frontmatter `description`; added the concrete before/after diff in section 5.
- **Round 2:** Added the troubleshooting decision order in section 7 and the "When the Rules Bend" edge-case catalog in section 6.
- **Round 3:** Created [references/anti-patterns.md](references/anti-patterns.md) with 10 named patterns (A1-A10), code examples, and a self-check checklist.
- **Round 4:** Added the pre-submit validation gates (hard/soft/meta) in section 8 and the in-flight observability signals in section 9.
- **Round 5 (this round):** Added the table of contents, the guideline-numbering quick-reference table, and these version notes. Polished cross-links so G1-G4 codes resolve to anchored sections and so A-codes resolve to the companion file.

**When to update this skill:**
- Source tweet or Karpathy follow-up posts a new guideline → add a section, bump to v1.1.
- A new recurring anti-pattern emerges in real diffs → append to the companion file as A11, A12, …
- A section becomes stale (e.g., tooling changes invalidate a `git diff --stat` tip) → revise in place, note in the change log above.

**License:** MIT (preserved as in frontmatter; attribution to Andrej Karpathy for the original observations linked in the intro).