import type { ToolCall } from "@langchain/core/messages";
import type { AIMessage } from "@langchain/langgraph-sdk";

import type { Translations } from "../i18n";
import { hasToolCalls } from "../messages/utils";

export function explainLastToolCall(message: AIMessage, t: Translations) {
  if (hasToolCalls(message)) {
    const lastToolCall = message.tool_calls![message.tool_calls!.length - 1]!;
    return explainToolCall(lastToolCall, t);
  }
  return t.common.thinking;
}

export function explainToolCall(toolCall: ToolCall, t: Translations) {
  return explainToolCallByNameAndArgs(toolCall.name, toolCall.args, t);
}

export function explainToolCallByNameAndArgs(
  name: string | undefined,
  args: unknown,
  t: Translations,
) {
  if (name === "web_search" || name === "image_search") {
    const query =
      args && typeof args === "object" && "query" in args
        ? (args as { query?: unknown }).query
        : undefined;
    if (typeof query === "string" && query) {
      return t.toolCalls.searchFor(query);
    }
    return t.toolCalls.searchForRelatedInfo;
  }

  if (name === "web_fetch") {
    const url =
      args && typeof args === "object" && "url" in args
        ? (args as { url?: unknown }).url
        : undefined;
    if (typeof url === "string" && url) {
      return `${t.toolCalls.viewWebPage}: ${url}`;
    }
    return t.toolCalls.viewWebPage;
  }

  if (name === "present_files") {
    return t.toolCalls.presentFiles;
  }

  if (name === "write_todos") {
    return t.toolCalls.writeTodos;
  }

  if (
    args &&
    typeof args === "object" &&
    "description" in args &&
    typeof (args as { description?: unknown }).description === "string"
  ) {
    return (args as { description: string }).description;
  }

  if (name) {
    return t.toolCalls.useTool(name);
  }

  return undefined;
}
