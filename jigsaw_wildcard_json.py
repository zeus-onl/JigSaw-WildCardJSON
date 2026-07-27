"""
===============================================================================
  ⚡ ZEUS.ONL - JigSaw Wildcard (JSON) ⚡
  Function: JSON-aware counterpart to Impact Pack's ImpactWildcardProcessor
  Author: Jigsaw & Zeus
  Official Network: https://zeus.onl
===============================================================================

WHY THIS NODE EXISTS
  Impact Pack's ImpactWildcardProcessor/ImpactWildcardEncode resolve wildcard
  syntax with a plain regex directly on the raw text:

      pattern = r'(?<!\\)\\{((?:[^{}]|(?<=\\)[{}])*?)(?<!\\)\\}'   # {opt1|opt2}
      pattern = r"__([\\w.\\-+/*\\\\]+?)__"                          # __wildcard__

  The random-choice syntax uses curly braces -- the exact same character
  JSON uses for objects. Feed a JSON prompt template straight into that
  regex and it can't tell a JSON object boundary from a wildcard group;
  it eats the structure and corrupts the output.

  This node sidesteps the conflict by resolving the JSON structure FIRST
  (json.loads), then walking the resulting tree and only handing the
  actual string leaf values -- never the structural braces -- to Impact
  Pack's existing wildcard engine (impact.wildcards.process). Everything
  Impact Pack already supports ({a|b}, __wildcard__, count$$, ::weight,
  <lora:...> tags) keeps working exactly as-is, just scoped per-leaf
  instead of globally over the raw text.
"""

import json
import hashlib

from server import PromptServer

try:
    import impact.wildcards as impact_wildcards
except Exception:
    impact_wildcards = None


def _leaf_seed(base_seed, path):
    """Derive a stable but distinct seed per JSON path so leaves that share
    the same wildcard options don't all resolve to the identical pick."""
    if base_seed is None:
        return None
    h = int(hashlib.md5(path.encode("utf-8")).hexdigest(), 16)
    return (int(base_seed) + h) % 0xFFFFFFFFFFFFFFFF


def _process_leaf(value, base_seed, path):
    if impact_wildcards is None:
        return value
    leaf_seed = _leaf_seed(base_seed, path)
    return impact_wildcards.process(text=value, seed=leaf_seed)


def _walk(node, base_seed, path=""):
    if isinstance(node, dict):
        return {k: _walk(v, base_seed, f"{path}/{k}") for k, v in node.items()}
    elif isinstance(node, list):
        return [_walk(v, base_seed, f"{path}[{i}]") for i, v in enumerate(node)]
    elif isinstance(node, str):
        return _process_leaf(node, base_seed, path)
    else:
        return node


def process_json_wildcards(json_text, seed=None):
    """
    Parses json_text as real JSON, resolves {a|b} / __wildcard__ syntax
    inside every string leaf via Impact Pack's wildcard engine, and returns
    the re-serialized JSON string with the same structure but resolved
    values. Raises json.JSONDecodeError if json_text isn't valid JSON.
    """
    data = json.loads(json_text)
    resolved = _walk(data, seed)
    return json.dumps(resolved, indent=2, ensure_ascii=False)


def process_auto(text, seed=None):
    """
    All-rounder entry point: figures out on its own whether 'text' is a
    JSON prompt template or a plain wildcard-style text prompt, and routes
    it to the right engine.

    - Tries json.loads() first. Only treats it as JSON mode if the parsed
      result is actually a dict or list (a bare quoted word or number is
      technically valid JSON too, but that's not what a JSON *prompt
      template* looks like, so it's routed to plain-text mode instead).
    - Anything that fails to parse, or parses to a non-container value,
      falls back to Impact Pack's original wildcard engine directly on
      the raw text -- identical behavior to ImpactWildcardProcessor.

    Returns (result_text, detected_mode) where detected_mode is "json" or
    "text", so callers/logs can show what was actually used.
    """
    data = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = None

    if isinstance(data, (dict, list)):
        resolved = _walk(data, seed)
        return json.dumps(resolved, indent=2, ensure_ascii=False), "json"

    # Plain-text fallback -- same engine ImpactWildcardProcessor uses
    if impact_wildcards is None:
        return text, "text"
    return impact_wildcards.process(text=text, seed=seed), "text"


class JigsawWildcardJSON:
    @classmethod
    def INPUT_TYPES(s):
        wildcard_list = ["Select the Wildcard to add to the text"]
        if impact_wildcards is not None:
            try:
                wildcard_list += impact_wildcards.get_wildcard_list()
            except Exception:
                pass

        return {
            "required": {
                "json_text": ("STRING", {
                    "multiline": True,
                    "dynamicPrompts": False,
                    "tooltip": "JSON prompt template. {a|b} and __wildcard__ syntax is "
                               "resolved only inside string values -- the JSON structure "
                               "itself is never touched by the wildcard regex.",
                }),
                "populated_text": ("STRING", {
                    "multiline": True,
                    "dynamicPrompts": False,
                    "tooltip": "The resolved JSON that is actually used at execution time, "
                               "same role as ImpactWildcardProcessor's populated_text.",
                }),
                "mode": (["populate", "fixed", "reproduce"], {
                    "default": "populate",
                    "tooltip": "populate: resolve wildcards fresh from json_text every run.\n"
                               "fixed: keep populated_text as-is, no re-resolving (editable).\n"
                               "reproduce: behaves like fixed once, for reproducing an exact "
                               "previous result, then falls back to populate.",
                }),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff,
                    "tooltip": "Seed for wildcard resolution. Each JSON leaf derives its own "
                               "sub-seed from this so identical option-lists in different "
                               "fields don't all pick the same value."}),
                "Select to add Wildcard": (wildcard_list,),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    CATEGORY = "🍳 Jigsaw/Prompt"
    DESCRIPTION = (
        "All-rounder counterpart to Impact Pack's ImpactWildcardProcessor. Auto-detects "
        "whether the input is a JSON prompt template or a plain wildcard-style text "
        "prompt:\n"
        "- If it parses as JSON (object/array), only the string leaf values are resolved "
        "for {a|b} / __wildcard__ syntax -- the JSON braces themselves are never touched, "
        "unlike feeding JSON directly into ImpactWildcardProcessor, which corrupts it.\n"
        "- If it's not JSON, it falls back to Impact Pack's original wildcard engine "
        "directly on the raw text -- identical behavior to ImpactWildcardProcessor.\n\n"
        "NOTE: mode currently affects processing only; the frontend auto-populate "
        "behavior Impact Pack has (JS overwriting populated_text before queue) is not "
        "wired up yet -- for now, edit/paste your template into json_text and rely on "
        "'populate' mode to resolve it into populated_text at run time."
    )
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("processed_text",)
    FUNCTION = "doit"

    @staticmethod
    def process(**kwargs):
        result, _ = process_auto(kwargs["text"], seed=kwargs.get("seed"))
        return result

    def doit(self, *args, **kwargs):
        mode = kwargs.get("mode", "populate")
        seed = kwargs.get("seed", 0)

        if mode == "fixed":
            source_text = kwargs["populated_text"]
        else:
            # populate / reproduce (reproduce's "stick to populated_text once" behavior
            # is a frontend concern in Impact Pack; server-side we just resolve fresh)
            source_text = kwargs["json_text"] if kwargs.get("json_text") else kwargs["populated_text"]

        result, detected_mode = process_auto(source_text, seed=seed)
        print(f"[JigsawWildcardJSON] Detected input as '{detected_mode}' mode.")

        # Push the resolved text back to the node's populated_text widget in the
        # frontend -- without this, populated_text stays visually empty/unchanged
        # even though the correct text was used for this execution.
        node_id = kwargs.get("unique_id")
        if node_id is not None:
            try:
                PromptServer.instance.send_sync(
                    "jigsaw-wildcard-json-populate",
                    {"node_id": node_id, "text": result},
                )
            except Exception as e:
                print(f"[JigsawWildcardJSON] Could not push populated_text update to UI: {e}")

        return (result,)


NODE_CLASS_MAPPINGS = {"JigsawWildcardJSON": JigsawWildcardJSON}
NODE_DISPLAY_NAME_MAPPINGS = {"JigsawWildcardJSON": "🍳 [ZEUS.ONL] Jigsaw Wildcard (JSON)"}
