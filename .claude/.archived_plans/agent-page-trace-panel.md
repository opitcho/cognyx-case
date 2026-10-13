# Agent page: replace the inspector with a single trace panel

## Target

The Agent page has two columns and no tabs.

```
┌ sidebar ┐ ┌ CHAT ───────────────────────────┐ ┌ AGENT WORK ─────────────────────────┐
│ pages   │ │ YOU                             │ │ ── Is the bogie frame reused? ──    │
│ tools   │ │ Is the bogie frame reused?      │ │ I need the BOM rows.        (italic)│
│ skills  │ │                                 │ │ ▸ run_sql · SELECT * FROM bom LIM…  │
│ session │ │ AGENT                           │ │ Checking the notes too.             │
│ agents  │ │ ▸ Reasoning                     │ │ ▾ run_sql · SELECT * FROM nope      │
│         │ │ Yes. BF-100 is reused in V1–V4. │ │   query   SELECT * FROM nope        │
│         │ │                                 │ │   RESULT  Error: no such table      │
│         │ │ YOU                             │ │ ── And the pantograph? ──           │
│         │ │ And the pantograph?             │ │ ✦ waiting for model…                │
│         │ │ [ Ask about a sub-assembly… ]   │ │                                     │
└─────────┘ └─────────────────────────────────┘ └─────────────────────────────────────┘
```

**Chat column (unchanged from today):** the user's messages, the agent's answers with their reasoning folded, the
approval prompt, the chat input.

**Agent work column (new):** one scrollable list, in the order the agent worked, that follows the latest step. It holds
three things and nothing else:

| What | How it is drawn |
|---|---|
| A question divider | One line with the user's message, clipped. Starts each turn, so the steps under it are the work done for that question. |
| The agent's reasoning and interim text | The reasoning of a step that made tool calls, in italics, and any text it wrote with the calls, as plain text. Shown in full, not folded: this column is the reasoning trace. |
| A tool call | One folded row per call: tool name and first argument (`run_sql · SELECT * FROM bom…`), red when the call failed. Unfolding it shows the arguments and the result underneath. A call still running shows "running…" in place of the result. |

The reasoning of a final answer stays in the chat, folded above that answer. It is not repeated on the right.

A compaction shows as one divider line (`⟲ 12 messages compacted · ~24k → ~6k tokens`), as today. The summary message
itself is not drawn.

## What is removed

All of this comes from the jean-code layout, where the timeline was a list of blocks and clicking one opened it in an
inspector.

| Removed | Why |
|---|---|
| The **Request**, **Context** and **Agent state** tabs | Not needed for the demo: raw request payload, usage table, compaction settings, agent attributes. |
| The **Activity** tab's two halves (block list + selected-block detail) | This is the redundancy: each block was drawn once as a card and again as the detail below. A tool call now opens in place. |
| Separate TOOL RESULT blocks, "Jump to result", "Jump to call" | The result is shown inside its call. |
| Block selection, "Follow latest", block numbers (`#12`), "context message 3 of 9", "Raw message" | They only served the inspector. |
| SYSTEM and HEAD END blocks | The system prompt and the context marker are not part of the agent's work on a question. |
| Header pills `turns`, `tool calls`, `in context`, `compacted`, `context ~24k / 256k` | Context-window bookkeeping. The header keeps the model, the status and the cost line. |

Kept as is: the sidebar (pages, tools, skills, reasoning effort, budget, agent picker), `/compact`, the compaction
toasts, the other three pages.

## Files

### `jean-code/src/app.py` (about 965 lines → about 700)

Purpose: the Streamlit app. Only the Agent page's right column and its helpers change.

New:

- `render_trace(entries: list[Entry], running: bool, agent) -> None`
  Draws the Agent work column: walks `entries` in order and draws a question divider for each `user` message, a
  compaction divider where messages left the context, and `render_step` for each message with tool calls or with
  reasoning only. Skips `agent`, `system`, `marker`, `summary` and `tool_result` messages (results are drawn by their
  call). Ends with the "waiting for model…" block while running. Replaces `render_timeline`.
- `render_step(entries: list[Entry], pos: int, running: bool, pending: bool) -> None`
  One assistant message: its reasoning (italic), its text, then one `st.expander` per tool call holding
  `render_args` and `render_output`, or "running…" / "waiting for approval" / "no result". Replaces
  `render_tool_call`.

Kept and reused: `Entry`, `sync_history`, `turn_kind`, `results_of`, `call_summary`, `parse_args`, `is_error`,
`render_args`, `render_output`, `render_chat`, `render_approval`, `show_reasoning`, `compaction_of`.

Deleted: `render_turn`, `render_tool_result`, `render_text`, `render_request`, `render_context`, `render_state`,
`select`, `call_of`, `call_names`, `preview`, `result_summary`, `to_jsonable`, `context_size`, `compaction_cost`,
`card`'s `num` argument, the constants `STATE_CONFIG`, `CONTEXT_CONFIG`, `STATE_HIDDEN`, `USAGE_COLUMNS`,
`MONO_KINDS`, `LONG_ARG` if unused, and `st.session_state.selected`.

`live_view` loses the tabs and the `selected` lookup: `chat_col` calls `render_chat`, `work_col` calls `render_trace`.
`render_header` loses the five pills listed above.

### `jean-code/src/app.css`

Purpose: the app's styles. Delete the rules for what is gone: the invisible hit-area button (`st-key-hit-`), the
selected card (`.tl-card.sel`), the tool-result elbow, the inspector head (`.insp-head`, `.badge`, `.insp-meta`),
`.fn-name`, the tabs. Add: the trace's scroll box filling the window like the chat's, the question divider, the
italic reasoning line, a red left edge on a failed call's row.

### `tests/test_app.py`

Purpose: the app starts and draws its pages. Rewrite the second test for the new column: with a seeded conversation
(one question, one call that succeeds, one that fails, one answer), the page has no tabs, the right column has two
expanders labelled with the calls, the failed call's result is inside its expander, and neither the question nor the
answer text appears as a step.

### `jean-code/README.md` and `jean-code/docs/screenshot.png`

The screenshot and its caption show the old timeline and inspector. Retake the screenshot and reword the caption
once the page is checked in a browser.

## Order of work

1. Check one behaviour first: an unfolded `st.expander` must stay unfolded while the page polls every 0.5 s and its
   content changes from "running…" to the result. Script under `.experiments/`, seeded agent, no model call. If it
   folds back, give each expander a stable `key` and keep the status out of its label.
2. Write `render_trace` and `render_step`, switch `live_view` to them, run the test.
3. Delete the functions, constants and CSS listed above; run the full suite.
4. Look at the page in Chrome with the seeded conversation from `.experiments/70_seeded_chat_agent.py`, fix spacing,
   retake the README screenshot.

## Decisions to confirm

1. **All turns or only the last one on the right.** Planned: all turns, separated by question dividers, scrolled to
   the latest. Alternative: only the work for the last question.
2. **Reasoning on the right shown in full.** Planned: in full, since the column is the trace. Alternative: folded
   like in the chat.
3. **Sidebar.** Tools, skills and the agent picker are also from jean-code. Planned: leave them. Say so if they
   should go too.
