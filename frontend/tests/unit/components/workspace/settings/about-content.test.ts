import { afterEach, expect, test, rs } from "@rstest/core";

const original = process.env.NEXT_PUBLIC_APP_VERSION;

afterEach(() => {
  rs.resetModules();
  if (original === undefined) {
    delete process.env.NEXT_PUBLIC_APP_VERSION;
  } else {
    process.env.NEXT_PUBLIC_APP_VERSION = original;
  }
});

test("aboutMarkdown heading interpolates the app version", async () => {
  process.env.NEXT_PUBLIC_APP_VERSION = "9.9.9-test";
  const { aboutMarkdown } =
    await import("@/components/workspace/settings/about-content");
  // The branded heading carries the version stamp.
  expect(aboutMarkdown).toContain("# 关于 智海·观澜 9.9.9-test");
  // Upstream attribution remains present without replacing the product brand.
  expect(aboutMarkdown).toContain(
    "[上游开源框架](https://github.com/bytedance/deer-flow)",
  );
});

test("aboutMarkdown heading reflects the package version when env is unset", async () => {
  delete process.env.NEXT_PUBLIC_APP_VERSION;
  const { APP_VERSION } = await import("@/version");
  const { aboutMarkdown } =
    await import("@/components/workspace/settings/about-content");
  // Positive: the heading carries the real resolved version. This catches an
  // empty or undefined APP_VERSION interpolation, not just removal of the
  // old literal.
  expect(aboutMarkdown).toContain(`# 关于 智海·观澜 ${APP_VERSION}`);
});
