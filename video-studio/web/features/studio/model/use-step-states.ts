"use client";

import { useMemo } from "react";

import { stepStates, type StepInfo } from "@/domain/steps";
import { useTimeline } from "@/features/scenes/model/use-scenes";

import { useStudio } from "./studio-context";

/** En qué punto está cada paso, a partir de lo que hay ahora en el estudio. */
export function useStepStates(): StepInfo[] {
  const { script, production, scenes, description, growth } = useStudio();
  const timeline = useTimeline();
  const timelineIssues = timeline.late.length > 0 || timeline.disordered;
  return useMemo(
    () =>
      stepStates({
        verdict: script.verdict,
        music: production.music !== "",
        scenes: scenes.items,
        timelineIssues,
        description: description.text.trim() !== "",
        score: growth.results.score?.total ?? null,
      }),
    [script.verdict, production.music, scenes.items, timelineIssues, description.text, growth.results.score],
  );
}
