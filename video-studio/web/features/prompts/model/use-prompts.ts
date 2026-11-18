"use client";

import { useStudio } from "@/features/studio/model/studio-context";

export const usePrompts = () => useStudio().prompts;
