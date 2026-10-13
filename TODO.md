# To do

## 3. Regenerate the data

Regenerate `data/raw/` with two or three cases that are ambiguous by construction, so the "ask the user" path has something sure to stop on.
Claims point at raw rows by number, so `data/claims.jsonl` has to be rebuilt after: rules first, then the batch run.

## 4. Make it obvious where the rules are

Done: see "The rules" in `README.md`.
Left open: a changed rule's old claims stay in the log (`--show` marks them `-` and `~`), because the log is only appended to.

## 5. Decide which layer of the data the app shows

There are three: the raw files, the data after the rules alone, and the data after the agent's and people's claims on top.
Decide what the user sees and when, in particular for the demo, and say on screen which layer is on display.
