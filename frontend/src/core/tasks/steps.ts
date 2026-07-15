/**
 * Subtask step model shared by the live (SSE) and reload (fetched) paths.
 *
 * Issue #3779: the subtask card used to keep only the latest subagent message,
 * so earlier steps flashed by and nothing survived a reload. A `SubtaskStep` is
 * the normalized, renderable unit of subagent progress — one assistant turn
 * (`kind: "ai"`, carrying its tool-call requests) or one tool result
 * (`kind: "tool"`, carrying the tool's output). The backend persists the same
 * shape as `subagent.step` run-event content; `messageToStep` mirrors that
 * shaping for the live `task_running` event, which still carries the raw message.
 */

export interface SubtaskStepToolCall {
  id?: string;
  name?: string;
  args?: unknown;
}

export interface SubtaskStep {
  message_index: number;
  kind: "ai" | "tool";
  text: string;
  truncated?: boolean;
  tool_calls?: SubtaskStepToolCall[];
  tool_name?: string;
  tool_call_id?: string;
}

type RawMessage = {
  type?: string;
  content?: unknown;
  name?: string;
  tool_call_id?: string;
  tool_calls?: { id?: string; name?: string; args?: unknown; [key: string]: unknown }[];
  [key: string]: unknown;
};

function contentToText(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((block) => {
        if (typeof block === "string") {
          return block;
        }
        if (block && typeof block === "object" && "text" in block) {
          const text = (block as { text?: unknown }).text;
          return typeof text === "string" ? text : "";
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

/**
 * Find the originating tool-call args for a tool-result step.
 *
 * The backend emits separate step events: AI steps carry `tool_calls` with args,
 * and the following tool-result steps only carry `tool_name`. To show a useful
 * label (e.g. the web_search query or web_fetch URL) on each tool-result row,
 * we walk backwards from the tool step to the nearest AI step that requested a
 * tool with the same name.
 *
 * This is heuristic: if a single AI step requests multiple tools with the same
 * name, we can only return the first match. In practice that is rare.
 */
export function findToolCallArgsForStep(
  steps: SubtaskStep[],
  toolStep: SubtaskStep,
): SubtaskStepToolCall | undefined {
  if (toolStep.kind !== "tool") {
    return undefined;
  }
  const index = steps.findIndex(
    (s) => s.message_index === toolStep.message_index,
  );
  if (index < 0) {
    return undefined;
  }
  for (let i = index - 1; i >= 0; i--) {
    const step = steps[i];
    if (step?.kind !== "ai" || !step.tool_calls?.length) {
      continue;
    }
    // Prefer exact tool_call_id match when both sides provide it.
    if (toolStep.tool_call_id) {
      const match = step.tool_calls.find(
        (call) => call.id === toolStep.tool_call_id,
      );
      if (match) {
        return match;
      }
    }
    // Fallback to name matching for payloads from older backends or tools that
    // omit tool_call_id.
    if (toolStep.tool_name) {
      const match = step.tool_calls.find(
        (call) => call.name === toolStep.tool_name,
      );
      if (match) {
        return match;
      }
    }
  }
  return undefined;
}

/** Normalize a raw subagent message (live `task_running` payload) into a step. */
export function messageToStep(
  message: RawMessage,
  messageIndex: number,
): SubtaskStep {
  const kind = message.type === "tool" ? "tool" : "ai";
  const step: SubtaskStep = {
    message_index: messageIndex,
    kind,
    text: contentToText(message.content),
  };

  if (kind === "tool") {
    step.tool_name = message.name;
    step.tool_call_id = message.tool_call_id;
  } else {
    step.tool_calls = (message.tool_calls ?? []).map((call) => ({
      id: call.id,
      name: call.name,
      args: call.args,
    }));
  }

  return step;
}

/**
 * Steps to render in the subtask card timeline (#3779). Interleaves the
 * subagent's assistant turns and tool steps, ordered by `message_index`:
 *
 * - tool steps are always kept (one "the subagent ran <tool>" row each);
 * - AI steps are kept only when they carry visible reasoning text — a turn that
 *   only requests tools (blank text) adds no information beyond the tool rows
 *   that follow it, so it is dropped;
 * - when the task is `completed`, a trailing AI step with no tool_calls is the
 *   subagent's final answer, which the card already renders as `task.result`,
 *   so it is dropped here to avoid showing the answer twice.
 */
export function stepsForDisplay(
  steps: SubtaskStep[] | undefined,
  status: "in_progress" | "completed" | "failed",
): SubtaskStep[] {
  const visible = (steps ?? [])
    .filter((step) => step.kind === "tool" || step.text.trim() !== "")
    .sort((a, b) => a.message_index - b.message_index);

  if (status === "completed") {
    const last = visible[visible.length - 1];
    if (last?.kind === "ai" && !last?.tool_calls?.length) {
      return visible.slice(0, -1);
    }
  }
  return visible;
}

type RunEvent = {
  event_type?: string;
  content?: unknown;
  metadata?: { task_id?: string } & Record<string, unknown>;
};

/**
 * Map persisted run events (from `GET /{rid}/events`) into the subtask's steps,
 * keeping only `subagent.step` events for `taskId` and ordering by message_index.
 * The persisted `content` already matches the step shape (it is what the backend
 * `build_subagent_step` produced), so this filters, projects, and sorts (#3779).
 */
export function eventsToSteps(
  events: RunEvent[],
  taskId: string,
): SubtaskStep[] {
  const steps: SubtaskStep[] = [];
  for (const event of events) {
    if (event.event_type !== "subagent.step") {
      continue;
    }
    const content = event.content as
      | (SubtaskStep & { task_id?: string })
      | undefined;
    const eventTaskId = content?.task_id ?? event.metadata?.task_id;
    if (!content || eventTaskId !== taskId) {
      continue;
    }
    steps.push({
      message_index: content.message_index,
      kind: content.kind,
      text: content.text ?? "",
      truncated: content.truncated,
      tool_calls: content.tool_calls,
      tool_name: content.tool_name,
      tool_call_id: content.tool_call_id,
    });
  }
  return steps.sort((a, b) => a.message_index - b.message_index);
}

/**
 * Merge `incoming` steps into `existing`, deduping by `message_index` (incoming
 * wins) and keeping the result ordered. Used to reconcile live SSE steps with
 * steps fetched on expand without double-rendering shared indices.
 */
export function mergeSteps(
  existing: SubtaskStep[],
  incoming: SubtaskStep[],
): SubtaskStep[] {
  const byIndex = new Map<number, SubtaskStep>();
  for (const step of existing) {
    byIndex.set(step.message_index, step);
  }
  for (const step of incoming) {
    byIndex.set(step.message_index, step);
  }
  return [...byIndex.values()].sort(
    (a, b) => a.message_index - b.message_index,
  );
}
