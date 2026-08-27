import { afterEach, describe, expect, test } from "@rstest/core";
import { cleanup, render, screen } from "@testing-library/react";

import { OnboardingDialog } from "@/components/workspace/onboarding/onboarding-dialog";
import { I18nContext } from "@/core/i18n/context";
import { enUS } from "@/core/i18n/locales/en-US";
import { zhCN } from "@/core/i18n/locales/zh-CN";

function renderWithLocale(locale: "zh-CN" | "en-US", open: boolean) {
  return render(
    <I18nContext.Provider
      value={{
        locale,
        setLocale: () => undefined,
        t: locale === "zh-CN" ? zhCN : enUS,
      }}
    >
      <OnboardingDialog open={open} onOpenChange={() => undefined} />
    </I18nContext.Provider>,
  );
}

afterEach(cleanup);

describe("OnboardingDialog", () => {
  test("renders the private-vs-external model guidance in zh-CN", () => {
    renderWithLocale("zh-CN", true);

    expect(screen.getByText("私有部署模型")).toBeTruthy();
    expect(screen.getByText("外部模型")).toBeTruthy();
    // The information-leak warning must be present
    expect(screen.getByText(/信息安全提醒/)).toBeTruthy();
  });

  test("renders all four modes with trade-offs in zh-CN", () => {
    renderWithLocale("zh-CN", true);

    expect(screen.getByText("闪速")).toBeTruthy();
    expect(screen.getByText("思考")).toBeTruthy();
    expect(screen.getByText("Pro")).toBeTruthy();
    expect(screen.getByText("Ultra")).toBeTruthy();
    // Trade-offs are surfaced, not only benefits
    expect(screen.getAllByText(/耗时/).length).toBeGreaterThan(0);
  });

  test("renders the en-US onboarding copy", () => {
    renderWithLocale("en-US", true);

    expect(screen.getByText("Privately deployed models")).toBeTruthy();
    expect(screen.getByText("External models")).toBeTruthy();
    expect(screen.getByText(/Security notice/)).toBeTruthy();
  });
});
