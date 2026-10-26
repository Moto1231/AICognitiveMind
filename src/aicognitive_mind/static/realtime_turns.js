// The Realtime model may finish its text before a remote MCP call finishes.
// Only the exact answer in a confirmed, matching completion may reach speech.
function objectValue(value) {
  if (typeof value === "string") {
    try { return objectValue(JSON.parse(value)); } catch (_) { return null; }
  }
  if (!value || typeof value !== "object" || value.isError === true) return null;
  if (value.structuredContent) return objectValue(value.structuredContent);
  if (Array.isArray(value.content)) {
    for (const entry of value.content) {
      if (entry.type === "text") {
        const parsed = objectValue(entry.text);
        if (parsed) return parsed;
      }
    }
    return null;
  }
  return value;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}

function samePayload(left, right) {
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

export class RealtimeTurns {
  constructor({ send, speak, fail, prepare = async () => "", setTimer = setTimeout, clearTimer = clearTimeout }) {
    Object.assign(this, { send, speak, fail, prepare, setTimer, clearTimer });
    this.queue = [];
    this.seenInputs = new Set();
    this.spokenKeys = new Set();
    this.calls = new Map();
    this.context = {};
    this.ready = false;
    this.closed = false;
    this.turn = null;
    this.instructions = "";
    this.completedResponses = new Set();
    this.retiredResponses = new Set();
    this.importTimer = this.setTimer(() => this.reject("Realtime interaction tools did not become ready."), 60_000);
  }

  close() {
    this.closed = true;
    this.clearTimer(this.timer);
    this.clearTimer(this.importTimer);
    this.queue = [];
    this.turn = null;
    this.calls.clear();
    this.context = {};
  }

  reject(message) {
    if (this.closed) return;
    this.close();
    this.fail(message);
  }

  async startNext() {
    if (this.closed || !this.ready || this.turn || !this.queue.length) return;
    const turn = this.queue.shift();
    this.turn = turn;
    this.timer = this.setTimer(() => this.reject("Realtime interaction timed out before a confirmed completion."), 180_000);
    this.requestResponse();
  }

  requestResponse(observation = "") {
    const turn = this.turn;
    if (!turn || this.closed) return;
    if (++turn.rounds > 8) return this.reject("Realtime interaction did not reach a confirmed completion.");
    if (turn.responseId) this.retiredResponses.add(turn.responseId);
    turn.done = false;
    turn.responseId = null;
    turn.pending.clear();
    turn.usedMcp = false;
    try { this.send({ type: "response.create", response: { instructions: this.instructions + "\n" +
      "Process only this finalized human turn. The exact user_message for BOTH begin_interaction and complete_interaction is " +
      JSON.stringify(turn.transcript) + (turn.key ? ". Preserve the completed begin_interaction and its recalled context. Working context: " : ". First call begin_interaction with host_working_context ") +
      JSON.stringify(turn.context || this.context) + ". Consult its result before reasoning. Complete with that unchanged begin key and " +
      "the exact intended spoken response_text. A successful completion has status=interaction_committed. " +
      "Carry the returned context; keep summary within 2000 characters. Do not answer other queued audio turns. " +
      (!turn.key ? "This first response must only call begin_interaction; wait for its result and the next response before completing or executing the requested task. " : "") +
      (turn.key ? "This turn already began with key " + JSON.stringify(turn.key) + "; do not begin again. " : "") +
      (turn.failedCompletion ? "Retry the failed completion once using exactly these unchanged arguments: " + JSON.stringify(turn.failedCompletion) + ". " : "") +
      (turn.observation ? "Current camera evidence: " + turn.observation : "")
    } }); } catch (error) { this.reject("Realtime connection failed: " + error.message); }
  }

  async finishOrContinue() {
    const turn = this.turn;
    if (this.closed || !turn || !turn.done || turn.pending.size || turn.finishing || turn.preparing) return;
    if (turn.committed) {
      turn.finishing = true;
      this.clearTimer(this.timer);
      try {
        if (!this.spokenKeys.has(turn.key)) {
          this.spokenKeys.add(turn.key);
          await this.speak(turn.committed.text, () => !this.closed && this.turn === turn);
        }
      } catch (error) {
        return this.reject("Voice playback failed: " + error.message);
      }
      if (this.closed || this.turn !== turn) return;
      this.context = turn.committed.context;
      if (turn.responseId) this.retiredResponses.add(turn.responseId);
      this.clearTimer(this.timer);
      this.turn = null;
      this.calls.clear();
      this.startNext();
    } else if (turn.usedMcp) {
      if (turn.key && !turn.prepared) {
        turn.preparing = true;
        try {
          turn.observation = await this.prepare(turn.transcript);
          if (this.closed || this.turn !== turn) return;
          turn.prepared = true;
          turn.preparing = false;
        } catch (error) {
          return this.reject("Realtime observation failed: " + error.message);
        }
      }
      this.requestResponse();
    } else {
      this.reject("Realtime response was not committed; spoken output was withheld.");
    }
  }

  completeCall(item) {
    const turn = this.turn;
    if (!turn || !item.id) return;
    const previous = this.calls.get(item.id) || {};
    if (previous.terminal) return;
    const call = { ...previous, ...item, terminal: true };
    this.calls.set(item.id, call);
    turn.pending.delete(item.id);
    turn.usedMcp = true;
    const args = objectValue(call.arguments);
    const result = objectValue(call.output);
    if (call.server_label !== "axiom") return this.reject("Unexpected Realtime tool server.");
    if (call.name === "begin_interaction") {
      if (turn.key || !args || args.user_message !== turn.transcript || result?.status !== "ready_to_reason" ||
          typeof result.idempotency_key !== "string" || !result.idempotency_key.trim() || call.error) {
        return this.reject("Realtime startup did not return a matching interaction key.");
      }
      turn.key = result.idempotency_key;
      turn.context = result.host_working_context || this.context;
    } else if (call.name === "complete_interaction") {
      if (!turn.key || !turn.prepared || !args || args.user_message !== turn.transcript || args.idempotency_key !== turn.key ||
          typeof args.response_text !== "string" || !args.response_text.trim()) {
        return this.reject("Realtime completion did not match the active interaction.");
      }
      if (turn.completionPayload && !samePayload(args, turn.completionPayload)) {
        return this.reject("Realtime completion retry changed the original payload.");
      }
      turn.completionPayload = args;
      if (call.error || result?.status !== "interaction_committed") {
        if (turn.failedCompletion) return this.reject("Realtime interaction could not be committed.");
        turn.failedCompletion = args;
      } else {
        if (result.interaction_trace_id !== turn.key) return this.reject("Realtime completion receipt did not match its key.");
        const context = objectValue(result.host_working_context);
        if (!context || typeof context.summary !== "string" || Array.from(context.summary).length > 2000) {
          return this.reject("Realtime completion returned invalid working context.");
        }
        turn.committed = { text: args.response_text, context };
      }
    } else if (call.error || !result) {
      return this.reject("Realtime tool call failed.");
    }
  }

  handle(event) {
    if (this.closed) return;
    if (event.type === "session.created" || event.type === "session.updated") {
      if (typeof event.session?.instructions === "string") this.instructions = event.session.instructions;
      return;
    }
    if (event.type === "conversation.item.done" && event.item?.type === "mcp_list_tools") {
      const item = event.item;
      const names = new Set((item.tools || []).map(tool => tool.name));
      if (item.server_label === "axiom" && names.has("begin_interaction") && names.has("complete_interaction")) {
        this.ready = true;
        this.clearTimer(this.importTimer);
        this.startNext();
      } else this.reject("Realtime interaction tools could not be imported.");
      return;
    }
    if (event.type === "mcp_list_tools.failed" || event.type === "error" || event.type === "conversation.item.input_audio_transcription.failed") {
      return this.reject(event.error?.message || "Realtime interaction failed.");
    }
    if (event.type === "conversation.item.input_audio_transcription.completed") {
      const transcript = event.transcript;
      if (typeof transcript !== "string" || !transcript.trim()) return;
      if (!event.item_id) return this.reject("Realtime transcription did not identify its turn.");
      if (this.seenInputs.has(event.item_id)) return;
      this.seenInputs.add(event.item_id);
      if (this.queue.length >= 8) return this.reject("Realtime input exceeded the pending turn limit.");
      this.queue.push({ transcript, itemId: event.item_id, rounds: 0, pending: new Set() });
      this.startNext();
      return;
    }
    const turn = this.turn;
    if (!turn) return;
    const responseId = event.response_id || event.response?.id;
    if (this.retiredResponses.has(responseId) ||
        (event.type === "response.done" && this.completedResponses.has(responseId))) return;
    if (event.type === "response.created") {
      turn.responseId = event.response?.id;
      return;
    }
    if (event.response_id && turn.responseId && event.response_id !== turn.responseId) return;
    if (event.type === "response.mcp_call_arguments.done") {
      const call = this.calls.get(event.item_id) || {};
      this.calls.set(event.item_id, { ...call, arguments: event.arguments });
    } else if (event.type === "response.mcp_call.in_progress") {
      if (!this.calls.get(event.item_id)?.terminal) turn.pending.add(event.item_id);
      turn.usedMcp = true;
    } else if (event.type === "response.output_item.done" && event.item?.type === "mcp_call") {
      this.completeCall(event.item);
    } else if (event.type === "response.mcp_call.failed") {
      // A terminal item supplies the attempted arguments and error. Without it
      // the turn remains blocked until timeout instead of guessing a receipt.
      turn.usedMcp = true;
      if (!this.calls.get(event.item_id)?.terminal) turn.pending.add(event.item_id);
    } else if (event.type === "response.done") {
      if (event.response?.id && turn.responseId && event.response.id !== turn.responseId) return;
      if (turn.done) return;
      if (event.response?.status && event.response.status !== "completed") return this.reject("Realtime response did not finish.");
      for (const item of event.response?.output || []) {
        if (item.type !== "mcp_call" || !item.id) continue;
        turn.usedMcp = true;
        if (item.output == null && !item.error) {
          if (!this.calls.get(item.id)?.terminal) turn.pending.add(item.id);
        } else this.completeCall(item);
      }
      turn.done = true;
      if (event.response?.id) this.completedResponses.add(event.response.id);
    }
    // output_text events are deliberately ignored: they are not commit receipts.
    this.finishOrContinue();
  }
}
