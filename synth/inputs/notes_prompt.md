You write one technical note as it would appear in the engineering change and
quality log of a rolling-stock manufacturer in northern France. The notes are
typed quickly by engineers and technicians on the shop floor.

You are given the facts of the note as JSON. Write only the text of the note:
no quotes, no explanation, one to three short sentences, 60 words at most.

## Style

Real notes of this kind look like this:

- `INSTALLED NEW GAUGE COVER GLASS ON L1 DOOR, INSALLED PACK AND CLOSED CONTAINER PER 25-66-01.RII ACCOPLISHED`
- `FLOOR PANEL CRACK, P/N:453T1996-12`
- `Actuator remplacé suite à NCR, do not reuse`

So: terse, abbreviations (qty, réf, cf, suite à, w/, P/N, NCR, FAI, BE for bureau
d'études), sometimes all upper case, sometimes a spelling mistake in an ordinary
word, no greeting, no signature. Vary the form from one note to the next.

## Language

- `fr`: French.
- `en`: English.
- `mixed`: French and English in the same note, as a bilingual team writes.

## References

- Write each reference exactly as given in `written_a` and `written_b`, character
  for character, even when it looks mistyped. Never correct, complete or reformat it.
- If `in_field` is true, `written_a` is already in the reference field of the note:
  you may leave it out of the text or repeat it.
- If `in_field` is false, `written_a` must appear in the text.
- `written_b`, when not empty, must appear in the text.
- `part_a` and `part_b` say what the two parts are. Stay consistent with them:
  do not call a relay a bracket. You may name the part, in the language of the note.
- Mention no other part reference, and nothing that looks like one: no code made
  of two capital letters followed by digits (no standard numbers, no note
  numbers, no drawing numbers of that shape).

## What the note states

`relation` says what the note must state. It must be clear to a careful reader,
but in the words an engineer would use, never the relation name itself.

- `same_as`: `written_a` and `written_b` are one and the same part (renumbered, alias, old reference).
- `not_same_as`: `written_a` and `written_b` are two different parts and must not be confused.
- `interchangeable_with`: `written_a` and `written_b` are equivalent, or `written_a` is an approved substitute for `written_b`.
- `functionally_equivalent_to`: `written_a` and `written_b` are different designs that do the same job and meet the same requirement.
- `superseded_by`: `written_a` has been replaced by `written_b`.
- `obsolete`: `written_a` must no longer be used on new designs. Name no replacement.
- `required_for`: `written_a` is needed because of `option` (for example a speed class).
- empty: the note states none of the above. It is a routine note on `topic`. If
  the topic asks for a word such as "equivalent", "obsolete" or "superseded", use
  it in the harmless sense described and state no relation between parts.

If `topic` says the note restates an earlier one, write it as a reminder.
