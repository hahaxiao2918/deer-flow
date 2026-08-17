"use client";

import { CloudIcon, LockIcon, ZapIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/core/i18n/hooks";
import { safeLocalStorage } from "@/core/settings/local";

const ONBOARDING_SEEN_KEY = "deerflow.onboarding-seen";

export function hasSeenOnboarding(): boolean {
  return safeLocalStorage.getItem(ONBOARDING_SEEN_KEY) === "true";
}

export function markOnboardingSeen() {
  safeLocalStorage.setItem(ONBOARDING_SEEN_KEY, "true");
}

/**
 * First-visit onboarding guide. Introduces the private-vs-external model
 * distinction (with the information-leak warning) and the four modes
 * (flash / thinking / pro / ultra) with their trade-offs.
 *
 * Auto-opens once per browser; the command palette exposes a "show again"
 * entry to reopen it. When `open`/`onOpenChange` are supplied, the dialog
 * runs fully controlled (command-palette path) and auto-open is skipped.
 */
export function OnboardingDialog({
  open: controlledOpen,
  onOpenChange,
}: {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const isControlled = controlledOpen !== undefined;

  useEffect(() => {
    if (!isControlled && !hasSeenOnboarding()) {
      setUncontrolledOpen(true);
    }
  }, [isControlled]);

  const open = isControlled ? controlledOpen : uncontrolledOpen;

  const handleOpenChange = (next: boolean) => {
    if (!isControlled) {
      setUncontrolledOpen(next);
    }
    if (!next) {
      markOnboardingSeen();
    }
    onOpenChange?.(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t.onboarding.title}</DialogTitle>
          <DialogDescription>{t.onboarding.subtitle}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5 text-sm">
          {/* Model safety section */}
          <section className="flex flex-col gap-2">
            <h3 className="font-medium">{t.onboarding.modelsTitle}</h3>
            <p className="text-muted-foreground">
              {t.onboarding.modelsIntro}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg border p-3">
                <div className="mb-1 flex items-center gap-2">
                  <LockIcon className="size-4 shrink-0" />
                  <span className="font-medium">
                    {t.onboarding.modelPrivateName}
                  </span>
                  <Badge variant="secondary">
                    {t.onboarding.modelPrivateTag}
                  </Badge>
                </div>
                <p className="text-muted-foreground text-xs">
                  {t.onboarding.modelPrivateDesc}
                </p>
              </div>
              <div className="rounded-lg border p-3">
                <div className="mb-1 flex items-center gap-2">
                  <CloudIcon className="size-4 shrink-0" />
                  <span className="font-medium">
                    {t.onboarding.modelExternalName}
                  </span>
                  <Badge variant="destructive">
                    {t.onboarding.modelExternalTag}
                  </Badge>
                </div>
                <p className="text-muted-foreground text-xs">
                  {t.onboarding.modelExternalDesc}
                </p>
              </div>
            </div>
            <p className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-2 text-xs">
              {t.onboarding.modelsWarning}
            </p>
          </section>

          {/* Modes section */}
          <section className="flex flex-col gap-2">
            <h3 className="flex items-center gap-2 font-medium">
              <ZapIcon className="size-4 shrink-0" />
              {t.onboarding.modesTitle}
            </h3>
            <p className="text-muted-foreground">{t.onboarding.modesIntro}</p>
            <div className="flex flex-col gap-2">
              {(
                [
                  {
                    name: t.onboarding.modeFlashName,
                    desc: t.onboarding.modeFlashDesc,
                    cons: t.onboarding.modeFlashCons,
                  },
                  {
                    name: t.onboarding.modeThinkingName,
                    desc: t.onboarding.modeThinkingDesc,
                    cons: t.onboarding.modeThinkingCons,
                  },
                  {
                    name: t.onboarding.modeProName,
                    desc: t.onboarding.modeProDesc,
                    cons: t.onboarding.modeProCons,
                  },
                  {
                    name: t.onboarding.modeUltraName,
                    desc: t.onboarding.modeUltraDesc,
                    cons: t.onboarding.modeUltraCons,
                  },
                ] as const
              ).map((mode) => (
                <div
                  key={mode.name}
                  className="flex flex-col gap-1 rounded-lg border p-3"
                >
                  <span className="font-medium">{mode.name}</span>
                  <span className="text-muted-foreground text-xs">
                    {mode.desc}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {mode.cons}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
