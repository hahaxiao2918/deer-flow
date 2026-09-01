import { createServer, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";

import { expect, test, type Locator } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

const THREAD_ID = "00000000-0000-0000-0000-00000000a001";
const RUN_ID = "00000000-0000-0000-0000-00000000a002";
const HUMAN_1_TEXT = "First deterministic question";
const STEP_1_TEXT = "FIRST TURN HISTORY STEP";
const ANSWER_1_TEXT = "First deterministic answer";
const HUMAN_2_TEXT = "Second deterministic question";
const STEP_2_TEXT = "SECOND TURN LIVE STEP";

const human1 = {
  type: "human",
  id: "human-1",
  content: [{ type: "text", text: HUMAN_1_TEXT }],
  run_id: "run-first",
};
const step1 = {
  type: "ai",
  id: "step-1",
  content: STEP_1_TEXT,
  tool_calls: [{ id: "tool-1", name: "web_search", args: {} }],
  run_id: "run-first",
};
const answer1 = {
  type: "ai",
  id: "answer-1",
  content: ANSWER_1_TEXT,
  run_id: "run-first",
};
const human2 = {
  type: "human",
  id: "human-2",
  content: [{ type: "text", text: HUMAN_2_TEXT }],
  run_id: RUN_ID,
};
const step2 = {
  type: "ai",
  id: "step-2",
  content: STEP_2_TEXT,
  tool_calls: [{ id: "tool-2", name: "read_file", args: {} }],
  run_id: RUN_ID,
};

function sse(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function streamedStep2Chunk() {
  return {
    content: STEP_2_TEXT,
    additional_kwargs: {},
    response_metadata: {},
    type: "AIMessageChunk",
    id: "step-2",
    tool_calls: [{ id: "tool-2", name: "read_file", args: {} }],
    invalid_tool_calls: [],
    usage_metadata: null,
    tool_call_chunks: [],
    chunk_position: null,
  };
}

async function startControlledStreamServer() {
  let initialResponse: ServerResponse | undefined;
  let reconnectResponse: ServerResponse | undefined;
  let resolveInitial!: () => void;
  let resolveReconnect!: () => void;
  const initialConnected = new Promise<void>((resolve) => {
    resolveInitial = resolve;
  });
  const reconnectConnected = new Promise<void>((resolve) => {
    resolveReconnect = resolve;
  });
  const server = createServer((request, response) => {
    response.writeHead(200, {
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "no-cache",
      "Content-Type": "text/event-stream",
      "Content-Location": `/threads/${THREAD_ID}/runs/${RUN_ID}`,
    });
    response.write(sse("metadata", { run_id: RUN_ID, thread_id: THREAD_ID }));
    response.write(sse("messages", [streamedStep2Chunk(), {}]));
    response.write(
      sse("values", {
        // Keep the first-turn step exclusively in paged history. If the SSE
        // snapshot included it, the stream itself could repair the missing
        // local ordering baseline and make the regression test pass for the
        // wrong reason.
        messages: [human1, answer1, human2, step2],
      }),
    );
    if (request.method === "POST") {
      initialResponse = response;
      resolveInitial();
    } else {
      reconnectResponse = response;
      resolveReconnect();
    }
  });

  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const { port } = server.address() as AddressInfo;
  return {
    url: `http://127.0.0.1:${port}/stream`,
    initialConnected,
    reconnectConnected,
    finishReconnect() {
      reconnectResponse?.write(
        sse("values", {
          messages: [human1, answer1, human2, step2],
        }),
      );
      reconnectResponse?.end(sse("end", {}));
    },
    async close() {
      initialResponse?.destroy();
      reconnectResponse?.destroy();
      server.closeAllConnections();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}

async function expectAbove(upper: Locator, lower: Locator) {
  await expect(upper).toBeVisible();
  await expect(lower).toBeVisible();
  const upperBox = await upper.boundingBox();
  const lowerBox = await lower.boundingBox();
  expect(upperBox).not.toBeNull();
  expect(lowerBox).not.toBeNull();
  expect(upperBox!.y).toBeLessThan(lowerBox!.y);
}

test("keeps first-turn history steps before a second streamed turn across refresh", async ({
  page,
}) => {
  test.setTimeout(60_000);
  const streamServer = await startControlledStreamServer();
  let resolveSubmittedRequest!: (request: {
    method: string;
    pathname: string;
  }) => void;
  const submittedRequest = new Promise<{
    method: string;
    pathname: string;
  }>((resolve) => {
    resolveSubmittedRequest = resolve;
  });
  let resolveReconnectRequest!: (request: {
    method: string;
    pathname: string;
  }) => void;
  const reconnectRequest = new Promise<{
    method: string;
    pathname: string;
  }>((resolve) => {
    resolveReconnectRequest = resolve;
  });
  mockLangGraphAPI(page, {
    threads: [
      {
        thread_id: THREAD_ID,
        title: "Two-turn ordering regression",
        // Deliberately omit step1 from the SDK checkpoint tail. It exists only
        // in the paged history API, matching the production failure mode.
        messages: [human1, answer1],
      },
    ],
    runStreamHandler: (route) => {
      resolveSubmittedRequest({
        method: route.request().method(),
        pathname: new URL(route.request().url()).pathname,
      });
      return route.continue({ url: streamServer.url });
    },
  });
  let finalHistory = false;
  await page.route(`**/api/threads/${THREAD_ID}/messages/page**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: (finalHistory
          ? [human1, step1, answer1, human2, step2]
          : [human1, step1, answer1]
        ).map((content, index) => ({
          run_id: index < 3 ? "run-first" : RUN_ID,
          seq: index + 1,
          content,
          metadata: { caller: "lead_agent" },
          created_at: `2026-09-01T00:00:0${index}Z`,
        })),
        has_more: false,
        next_before_seq: null,
      }),
    }),
  );
  await page.route(
    `**/api/langgraph/threads/${THREAD_ID}/runs/${RUN_ID}`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: RUN_ID,
          thread_id: THREAD_ID,
          assistant_id: "lead_agent",
          status: "running",
          metadata: {},
          kwargs: {},
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-01T00:00:00Z",
        }),
      }),
  );
  await page.route(
    `**/api/langgraph/threads/${THREAD_ID}/runs/${RUN_ID}/stream**`,
    (route) => {
      resolveReconnectRequest({
        method: route.request().method(),
        pathname: new URL(route.request().url()).pathname,
      });
      return route.continue({ url: streamServer.url });
    },
  );

  try {
    await page.addInitScript(() => {
      window.localStorage.setItem("deerflow.onboarding-seen", "true");
    });
    await page.goto(`/workspace/chats/${THREAD_ID}`);
    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });
    await expect(textarea).toBeEnabled();
    await textarea.fill(HUMAN_2_TEXT);
    const submit = page.locator("button[type='submit']");
    await expect(submit).toHaveCount(1);
    await expect(submit).toBeVisible();
    await expect(submit).toBeEnabled();
    await submit.click();
    const submitted = await submittedRequest;
    expect(submitted.method).toBe("POST");
    expect(submitted.pathname).toBe(
      `/api/langgraph/threads/${THREAD_ID}/runs/stream`,
    );
    await streamServer.initialConnected;

    await expectAbove(
      page.getByText(STEP_1_TEXT),
      page.getByText(HUMAN_2_TEXT),
    );
    await expectAbove(
      page.getByText(HUMAN_2_TEXT),
      page.getByText(STEP_2_TEXT),
    );

    await page.reload();
    const joined = await reconnectRequest;
    expect(joined.method).toBe("GET");
    expect(joined.pathname).toBe(
      `/api/langgraph/threads/${THREAD_ID}/runs/${RUN_ID}/stream`,
    );
    await streamServer.reconnectConnected;
    await expectAbove(
      page.getByText(STEP_1_TEXT),
      page.getByText(HUMAN_2_TEXT),
    );
    await expectAbove(
      page.getByText(HUMAN_2_TEXT),
      page.getByText(STEP_2_TEXT),
    );

    finalHistory = true;
    streamServer.finishReconnect();
    await expectAbove(
      page.getByText(STEP_1_TEXT),
      page.getByText(HUMAN_2_TEXT),
    );
    await page.reload();
    await expectAbove(
      page.getByText(STEP_1_TEXT),
      page.getByText(HUMAN_2_TEXT),
    );
    await expectAbove(
      page.getByText(HUMAN_2_TEXT),
      page.getByText(STEP_2_TEXT),
    );
  } finally {
    await streamServer.close();
  }
});
