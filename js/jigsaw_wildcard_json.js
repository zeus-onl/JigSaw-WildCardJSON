// ===========================================================================
//  ZEUS.ONL - JigSaw Wildcard (JSON) - frontend widget behavior
//
//  Replicates Impact Pack's "Select to add Wildcard" dropdown behavior:
//  picking an entry from the dropdown inserts its __path/name__ text into
//  the json_text textbox at the top, instead of just sitting there selected.
//
//  Reuses Impact Pack's existing '/impact/wildcards/list' API endpoint --
//  this node already depends on Impact Pack being installed (imports
//  impact.wildcards server-side), so the endpoint is guaranteed to exist.
// ===========================================================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

let wildcards_list = [];

async function load_wildcards() {
	try {
		const res = await api.fetchApi('/impact/wildcards/list');
		const data = await res.json();
		wildcards_list = data.data || [];
	} catch (error) {
		console.error('[JigsawWildcardJSON] Failed to load wildcard list (is Impact Pack installed?):', error);
	}
}

load_wildcards();

const SELECT_LABEL = "Select the Wildcard to add to the text";

function is_wildcard_label(value) {
	return value === SELECT_LABEL;
}

app.registerExtension({
	name: "zeus.onl.JigsawWildcardJSON",

	async setup() {
		// Server pushes the resolved text here after each execution of doit();
		// this is what actually makes populated_text show something, since
		// ComfyUI doesn't auto-mirror STRING outputs into same-named widgets.
		api.addEventListener("jigsaw-wildcard-json-populate", (event) => {
			const { node_id, text } = event.detail || {};
			if (node_id === undefined) return;

			const node = app.graph.getNodeById(Number(node_id)) ?? app.graph.getNodeById(node_id);
			if (!node) return;

			const populated_widget = node.widgets?.find((w) => w.name === "populated_text");
			if (!populated_widget) return;

			populated_widget.value = text;
			app.canvas.setDirty(true);
		});
	},

	async nodeCreated(node) {
		if (node.comfyClass !== "JigsawWildcardJSON") return;

		const tbox_widget = node.widgets.find((w) => w.name === "json_text");
		const combo_widget = node.widgets.find((w) => w.name === "Select to add Wildcard");
		const populated_widget = node.widgets.find((w) => w.name === "populated_text");
		const mode_widget = node.widgets.find((w) => w.name === "mode");

		// populated_text is read-only while mode == 'populate' (it's driven by the
		// server after execution), but editable in 'fixed'/'reproduce' -- same as
		// Impact Pack's ImpactWildcardProcessor.
		if (populated_widget && mode_widget && populated_widget.inputEl) {
			const applyDisabled = () => {
				populated_widget.inputEl.disabled = mode_widget.value === "populate";
			};
			applyDisabled();
			const orig_callback = mode_widget.callback;
			mode_widget.callback = (...args) => {
				orig_callback?.apply(mode_widget, args);
				applyDisabled();
			};
		}

		if (!tbox_widget || !combo_widget) return;

		node._wildcard_value = SELECT_LABEL;

		// Whenever the dropdown fires its callback (i.e. the user picked an entry),
		// append the picked wildcard spec into json_text -- same UX as Impact Pack.
		combo_widget.callback = async (value, canvas, node, pos, e) => {
			if (!node) return;
			if (tbox_widget.value != '' && !tbox_widget.value.endsWith('\n') && !tbox_widget.value.endsWith(' '))
				tbox_widget.value += ', ';
			tbox_widget.value += node._wildcard_value;
		};

		// The dropdown never actually "keeps" a selection -- it always shows the
		// static label, and the real picked value is stashed in node._wildcard_value.
		Object.defineProperty(combo_widget, "value", {
			set: (value) => {
				if (!is_wildcard_label(value)) node._wildcard_value = value;
			},
			get: () => SELECT_LABEL,
		});

		// Force the dropdown's option list to always reflect the live wildcard list,
		// regardless of what was baked into INPUT_TYPES at node-registration time.
		Object.defineProperty(combo_widget.options, "values", {
			set: (_x) => {},
			get: () => wildcards_list,
		});

		// Don't persist "a wildcard was selected" into the saved workflow JSON --
		// always serialize back to the neutral label, matching Impact Pack.
		combo_widget.serializeValue = () => SELECT_LABEL;

		// Refresh the list once more in case Impact Pack's own load finished after ours.
		await load_wildcards();
	},
});
