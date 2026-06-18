# Anti-Patterns Catalog

A reference of common LLM coding anti-patterns that violate the Karpathy guidelines, with the violation, the smell, and the fix. Use this as a checklist when reviewing a diff you are about to commit, or when an LLM has produced output and you need to spot-check it.

Each entry maps to a guideline number from the parent `SKILL.md`. If you find yourself producing one of these, stop and rewrite.

---

## A1. Speculative Configuration

**Guideline violated:** 2 (Simplicity First)

**Smell:** Parameters, flags, or env vars that no current caller uses.

```python
# ANTI-PATTERN
def fetch_user(user_id, *, include_deleted=False, fallback_to_cache=True,
               timeout=30, retry_on_timeout=True, locale="en_US"):
    ...
```

**Why it's wrong:** Every flag is a future commitment — tests, docs, and combinatorics. If no caller passes `include_deleted`, the parameter is dead weight that still needs maintenance.

**Fix:** Drop the flag. Add it the day a caller actually needs it. If you find yourself wanting 3 flags, you probably want a different function.

---

## A2. Defensive Coding for Impossible Inputs

**Guideline violated:** 2 (Simplicity First)

**Smell:** Validating inputs that the type system or call site already guarantees.

```python
# ANTI-PATTERN
def add(a: int, b: int) -> int:
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("expected int")
    if a < 0 or b < 0:
        raise ValueError("negatives not allowed")
    return a + b
```

**Why it's wrong:** The signature is `int, int -> int`. Callers passing strings or negatives are bugs, not edge cases. The checks add runtime cost, mask bugs at the call site, and make the function harder to compose.

**Fix:** Trust the type. If a caller violates the contract, let it crash loudly at the boundary where the violation occurs.

---

## A3. Wrapper Functions with No Behavior

**Guideline violated:** 2 (Simplicity First)

**Smell:** A function that just renames or forwards to another function.

```python
# ANTI-PATTERN
def get_user_name(user):
    return user.name

def compute_total_price(cart):
    return cart.total_price
```

**Why it's wrong:** Adds an indirection layer with no transformation, no validation, and no abstraction value. Forces readers to jump to the definition for nothing.

**Fix:** Inline the call. Use `user.name` directly. Add a wrapper only if it will gain behavior (logging, caching, error handling — and only when that behavior is requested).

---

## A4. Format-Only Diffs

**Guideline violated:** 3 (Surgical Changes)

**Smell:** Reformatting code that wasn't part of the task — quotes, indentation, import order, trailing commas, type-hint style.

```diff
- from foo import bar, baz
+ from foo import (
+     bar,
+     baz,
+ )
```

**Why it's wrong:** Pollutes the diff, makes `git blame` useless, and may conflict with formatter config elsewhere in the file.

**Fix:** Run the project's auto-formatter on save, not as part of an unrelated task. If you must reformat, do it in a separate commit with a clear message.

---

## A5. "While I'm Here" Refactors

**Guideline violated:** 3 (Surgical Changes)

**Smell:** Touching adjacent code, dead variables, or "while I'm in this function" cleanups.

```python
# User asked: fix the null check in parse()
# LLM "helpfully" also: renames parse() to parse_input(),
#                       rewrites the inner for-loop as a comprehension,
#                       deletes an unused helper two files away.
```

**Why it's wrong:** Each unrelated change is a place for bugs to hide in review. The user can't reject one and accept the other — it's all one diff.

**Fix:** Make exactly the change requested. Mention the others as follow-ups: "I noticed X is also broken; want a separate change?"

---

## A6. "I'll Just Add a Test" Without Verifying It Tests the Right Thing

**Guideline violated:** 4 (Goal-Driven Execution)

**Smell:** A test that passes for the wrong reason — mocks the unit under test, asserts on trivial output, or never fails even when the bug is present.

```python
# ANTI-PATTERN
def test_process_items_handles_empty_list():
    process_items([])  # no assertion; passes as long as it doesn't crash
    assert True
```

**Why it's wrong:** A green test that doesn't exercise the bug is worse than no test — it gives false confidence.

**Fix:** Write the test against the *behavior* the user described. Confirm the test fails on the buggy version *before* applying the fix. If it passes on the bug, the test is broken.

---

## A7. Silent Scope Expansion

**Guideline violated:** 1 (Think Before Coding)

**Smell:** The user asked for one thing; the diff does three.

```
User:  "Add a logout button"
Diff:  + logout button
       + logout API endpoint
       + session-invalidation middleware
       + frontend route guard
       + tests for all of the above
```

**Why it's wrong:** The user wanted visibility into the cost. Silent scope expansion is how a 30-minute task becomes a 3-day PR.

**Fix:** After understanding the task, *list* the sub-pieces you're considering. Ask: "The logout button is straightforward. Do you also want the server-side session cleanup, or just the UI for now?"

---

## A8. "Defense in Depth" Error Handling

**Guideline violated:** 2 (Simplicity First) and 7 (Troubleshooting)

**Smell:** Try/except around code that doesn't raise, broad `except Exception`, or logging the same error at multiple layers.

```python
# ANTI-PATTERN
try:
    user = db.get_user(uid)
except Exception as exc:
    log.error("db lookup failed: %s", exc)
    try:
        user = cache.get_user(uid)
    except Exception as exc2:
        log.error("cache lookup also failed: %s", exc2)
        user = None
```

**Why it's wrong:** If the code is defensive for a real reason, keep it. If it's defensive "just in case", it hides the real failure and makes the call graph unreadable.

**Fix:** Pick the layer that owns the error and let it surface. Catch only at boundaries you control (e.g., the HTTP handler). Don't log-and-swallow.

---

## A9. Type-Hint Theater

**Guideline violated:** 2 (Simplicity First)

**Smell:** Overly precise types where the runtime doesn't care, or types that obscure intent.

```python
# ANTI-PATTERN
def parse_headers(
    raw: bytes,
) -> dict[str, list[tuple[str, str | None]]] | None:
    ...
```

**Why it's wrong:** The type is technically correct but forces every caller to reason about nested generics for a function they just want to call.

**Fix:** Use the simplest type that documents the contract. `dict[str, list[str]]` is fine. If the precise shape matters at the call site, the call site should enforce it.

---

## A10. Clever-for-Clever's-Sake

**Guideline violated:** 2 (Simplicity First)

**Smell:** One-liners, walrus operators, dict comprehensions, and metaprogramming where a 3-line version is clearer.

```python
# ANTI-PATTERN
result = {k: v for k, v in ((k, compute(k)) for k in keys) if v is not None}
```

**Why it's wrong:** Cleverness is a tax on the next reader (often future-you at 2am). Boring code is reviewable code.

**Fix:** Expand to the obvious form. If a reviewer has to re-parse it twice, it's wrong.

---

## Quick Self-Check Before Committing

Before you submit a diff, scan for these:

- [ ] Every changed line traces to a user-stated requirement (Guideline 3)
- [ ] No new parameters, flags, or env vars that have no caller (A1)
- [ ] No input validation the type system already enforces (A2)
- [ ] No renamed-forwarder functions (A3)
- [ ] No format-only changes mixed with logic changes (A4)
- [ ] No "while I'm here" cleanups of adjacent code (A5)
- [ ] Every new test fails on the buggy version (A6)
- [ ] No silent scope expansion vs. what the user asked (A7)
- [ ] No nested try/except or log-and-swallow (A8)
- [ ] No type hints that obscure rather than clarify (A9)
- [ ] No clever one-liners where 3 lines are clearer (A10)

If any box fails, fix it before submitting.
