import { describe, expect, test } from "@rstest/core";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { OnboardingDialog } from "@/components/workspace/onboarding/onboarding-dialog";
import { I18nContext } from "@/core/i18n/context";

function renderWithLocale(locale: "zh-CN" | "en-US", open: boolean) {
  return renderToStaticMarkup(
    createElement(
      I18nContext.Provider,
      {
        value: {
          locale,
          setLocale: () => undefined,
        },
      },
      createElement(OnboardingDialog, { open, onOpenChange: () => undefined }),
    ),
  );
}

describe("OnboardingDialog", () => {
  test("renders the private-vs-external model guidance in zh-CN", () => {
    const markup = renderWithLocale("zh-CN", true);

    expect(markup).toContain("私有部署模型");
    expect(markup).toContain("外部模型");
    // The information-leak warning must be present
    expect(markup).toContain("信息安全提醒");
  });

  test("renders all four modes with trade-offs in zh-CN", () => {
    const markup = renderWithLocale("zh-CN", true);

    expect(markup).toContain("闪速");
    expect(markup).toContain("思考");
    expect(markup).toContain("Pro");
    expect(markup).toContain("Ultra");
    // Trade-offs are surfaced, not only benefits
    expect(markup).toContain("耗时");
  });

  test("renders the en-US onboarding copy", () => {
    const markup = renderWithLocale("en-US", true);

    expect(markup).toContain("Privately deployed models");
    expect(markup).toContain("External models");
    expect(markup).toContain("Security notice");
  });
});
