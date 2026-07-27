# JigSaw Wildcard (JSON) 🍳

**Author:** Jigsaw & Zeus — [zeus.onl](https://zeus.onl)
**Category:** `🍳 Jigsaw/Prompt`
**Node class:** `JigsawWildcardJSON`

An all-rounder wildcard processor for ComfyUI that understands **both** plain
wildcard-style text prompts and **structured JSON prompt templates** — without
corrupting the JSON structure, which is what happens when you feed JSON into
Impact Pack's `ImpactWildcardProcessor`.

---

## Why this node exists

Impact Pack's wildcard engine (`ImpactWildcardProcessor` / `ImpactWildcardEncode`)
resolves `{option1|option2}` random-choice syntax with a regex that runs
directly on the raw text:

```
pattern = r'(?<!\\)\{((?:[^{}]|(?<=\\)[{}])*?)(?<!\\)\}'   # {opt1|opt2}
pattern = r"__([\w.\-+/*\\]+?)__"                            # __wildcard__
```

The problem: JSON also uses curly braces `{ }` — for objects, not random
choices. Feed a JSON prompt template into that regex and it can't tell a JSON
object boundary from a wildcard group. It matches across the JSON's own
structure and either strips the braces out entirely or produces broken,
non-JSON output. If you've ever fed a JSON prompt template into
`ImpactWildcardProcessor` and watched `populated_text` come back as mangled,
brace-less fragments instead of valid JSON — this is why.

**JigsawWildcardJSON** avoids the conflict by resolving the JSON structure
*first* (`json.loads()`), then walking the resulting tree and only handing the
actual **string leaf values** — never the structural braces — to Impact Pack's
existing wildcard engine (`impact.wildcards.process`). Everything Impact Pack
already supports (`{a|b}`, `__wildcard__`, `count$$`, `::weight`, `<lora:...>`
tags) keeps working exactly as-is, just scoped per-leaf instead of globally
over the raw text.

## Auto-detection: JSON or plain text

You don't have to tell the node what kind of input you're giving it — it
figures it out on its own:

- **Parses as JSON** (a real object or array) → JSON mode. Only the string
  leaf values are resolved for wildcard syntax; the JSON braces themselves are
  never touched.
- **Doesn't parse as JSON** (or parses to something that isn't a
  dict/list, like a bare word) → falls back to Impact Pack's original
  wildcard engine directly on the raw text — identical behavior to
  `ImpactWildcardProcessor`.

Either way you get a working result. Check the console for
`[JigsawWildcardJSON] Detected input as 'json'/'text' mode.` to confirm which
path was taken.

## Requirements

- **[ComfyUI-Impact-Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack)**
  must be installed. This node doesn't reimplement the wildcard engine — it
  imports `impact.wildcards` and reuses it directly, so the two wildcard
  systems (plain-text and JSON-aware) always stay in sync and share the same
  wildcard file library.
- If Impact Pack isn't found, the node degrades gracefully (JSON mode still
  works structurally, but no `{a|b}`/`__wildcard__` resolution will happen —
  text is passed through unchanged).

## Installation

1. Drop this folder into `ComfyUI/custom_nodes/` as `JigSaw-WildCardJSON`.
2. Restart ComfyUI completely (not just a node reload — the JS frontend
   extension only loads on server start).
3. Find the node under **🍳 Jigsaw/Prompt → Jigsaw Wildcard (JSON)**.

## Inputs

| Input | Type | Description |
|---|---|---|
| `json_text` | STRING (multiline) | Your JSON prompt template, or a plain wildcard-style text prompt. `{a|b}` / `__wildcard__` syntax is resolved only inside string values — the JSON structure itself is never touched. |
| `populated_text` | STRING (multiline) | The resolved output, pushed here automatically after each run. Editable when `mode` is `fixed`/`reproduce`; read-only while `mode` is `populate`. |
| `mode` | `populate` / `fixed` / `reproduce` | `populate`: resolve wildcards fresh from `json_text` every run. `fixed`: use `populated_text` as-is, no re-resolving. `reproduce`: same as fixed, for pinning down a specific past result. |
| `seed` | INT | Seed for wildcard resolution. Each JSON leaf derives its own sub-seed from this (via a path-based hash) so identical option-lists in different fields don't all resolve to the same pick. |
| `Select to add Wildcard` | dropdown | Pulls the live wildcard list from Impact Pack's own `/impact/wildcards/list` endpoint. Picking an entry inserts its `__path/name__` spec into `json_text` at the current text — same UX as `ImpactWildcardProcessor`. |

## Output

| Output | Type | Description |
|---|---|---|
| `processed_text` | STRING | The fully resolved text/JSON, ready to feed into your text encoder / conditioning node. |

## Example

Plain text mode:
```
{a woman|a man} with {short|long} hair, __quality__
```

JSON mode:
```json
{
  "subject": "{a woman|a man} with {short|long} hair",
  "style": "__quality__",
  "camera": {
    "shot": "{close-up|medium shot|wide shot}",
    "lens": "85mm"
  }
}
```
Only the string values (`"{a woman|a man}..."`, `"__quality__"`,
`"{close-up|...}"`, `"85mm"`) get scanned for wildcard syntax. The JSON keys,
nesting, and overall structure survive untouched.

## How the live update works

Since ComfyUI doesn't automatically mirror a node's STRING output back into a
same-named input widget, this node pushes the resolved result back to
`populated_text` itself: after `doit()` runs, the Python side calls
`PromptServer.instance.send_sync("jigsaw-wildcard-json-populate", ...)` with
the node's own ID, and the bundled JS extension listens for that event and
writes the text into the widget. This is why the node needs a full ComfyUI
restart after install/update — both the hidden `unique_id` input and the JS
listener are wired up at load time.

## Known limitations

- The dropdown wildcard list and the resolution engine are both borrowed
  directly from Impact Pack — if Impact Pack changes its wildcard file format
  or API route, this node inherits that change automatically (usually a good
  thing, occasionally worth a changelog check).
- No dedicated escaping syntax for a literal `{` or `}` inside a JSON string
  value beyond what Impact Pack's own escaping (`\{`, `\}`) already provides.

## License note

This node depends on and imports from **ComfyUI-Impact-Pack**, which is
licensed under **GPLv3**. If you plan to redistribute this node publicly,
factor that dependency into your own license choice.

---

*Part of the Jigsaw node collection — [zeus.onl](https://zeus.onl)*
