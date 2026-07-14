import type { Translations } from "@/core/i18n/locales/types";

import type { Skill } from "./type";

export function getSkillDisplayText(
  skill: Skill,
  t: Translations,
): { displayName: string; description: string } {
  const entry = t.skillCatalog?.[skill.name];
  if (entry) {
    return {
      displayName: entry.displayName,
      description: entry.description,
    };
  }
  return {
    displayName: skill.name,
    description: skill.description,
  };
}
