// The kinetic family (references/kinetic.md): key figures and key words set over the footage on their spoken words,
// opt-in per style (style.json graphics.kinetic; plan.py passes these types only then). Each format is one file here;
// Templates.tsx registers them all as floating templates (no card under them), and StyleEdit.tsx hides the word
// captions while one is up. The names never collide with plan.py TYPE_ONLY (the removed type cards).
import type React from "react";
import type { TP } from "../Templates";
import { CtaFollow } from "./CtaFollow";
import { GoalBar } from "./GoalBar";
import { KineticNumber } from "./KineticNumber";
import { KineticTitle } from "./KineticTitle";
import { NumberChain } from "./NumberChain";
import { StatStack } from "./StatStack";
import { StepBuild } from "./StepBuild";

export const KINETIC: Record<string, React.FC<TP>> = {
  kinetic_number: KineticNumber,
  number_chain: NumberChain,
  goal_bar: GoalBar,
  step_build: StepBuild,
  stat_stack: StatStack,
  kinetic_title: KineticTitle,
  cta_follow: CtaFollow,
};

/** Does this card hide the word captions while it is up? A kinetic card does unless its props say
 *  hide_captions: false; any other card does only when its props say hide_captions: true. */
export const hidesCaptions = (anim?: { type?: string; props?: Record<string, unknown> }) => {
  if (!anim?.type) return false;
  const v = anim.props?.hide_captions;
  return typeof v === "boolean" ? v : anim.type in KINETIC;
};
