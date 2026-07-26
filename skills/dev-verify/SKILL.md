---
name: dev-verify
description: Start the dev server and hand the visual check to the user. Use when a change needs to be seen in a browser — UI, styling, layout, or any user-facing behavior. Starts the server, waits for its port, then reports the URL and a specific list of what to click and confirm.
when_to_use: A UI or user-facing change is done and needs eyes on it; asked to run or start the app; about to verify something visual.
argument-hint: "[project dir — defaults to cwd; repeat for backend + frontend]"
allowed-tools: Bash, Read, Grep, Glob
---

# Hand the visual check to the user

You do not look at the UI. You start the server, then tell the user exactly what
to check. They have the browser open; you don't.

**Do not screenshot, drive a browser, or infer what the page looks like.** It
burns tokens, and a description of a screenshot is not evidence the feature
works. The user glancing at the screen is faster and more reliable than any
amount of reasoning about the code.

## 1. Start the server

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/start-dev.sh" [project-dir] [port]
```

The dev command and port come from `detect-stack.py`, so this works on any
recognized project. **For a split backend/frontend, run it once per directory,
backend first** — the frontend calls it, so a UI check without it is meaningless.

- **Exit 0** = up, URL printed.
- **Exit 1** = it didn't come up; the script prints the tail of its log. Read the
  failure and fix it. Don't hand the user a broken app and ask them to look.

The port is a conventional default for the detected framework, not read from
config. If the project overrides it, pass the real one as the second argument.

## 2. Hand off

Report the URL and a **specific, ordered checklist** derived from what you
actually changed. Ground every item in the change — not a generic smoke test.

Each item names where to go, what to do, and what should happen. The user should
be able to run it without reading the diff.

> Server is up — **http://localhost:5173**
>
> I changed how tasks move between lists. Please check:
>
> 1. Open a group with two lists that both have tasks
> 2. Drag a task from the first list to the second — it should land where you
>    dropped it, *not at the bottom*
> 3. Refresh — the task should still be in the second list
> 4. Open the same group in a second tab and repeat: the move should appear in
>    both tabs without a refresh
>
> Anything I should know about what you see?

Rules for the checklist:

- **Cover what you changed, plus what you might have broken.** If you touched
  shared code, include the neighbouring flow that also uses it.
- **Include the failure you'd expect if you got it wrong**, so a passing check
  is real information — *"should land where you dropped it, not at the bottom"*.
- Call out anything needing specific state: logged in, a group with members, two
  tabs for realtime behavior, an overdue item.
- Three sharp items beat ten vague ones.
- If the change has no visual surface, don't invoke this skill at all.

## 3. Wait

Stop after handing off. **The user's answer is the verification result.** Treat a
reported problem as the bug report and fix it — don't argue with what they saw.
