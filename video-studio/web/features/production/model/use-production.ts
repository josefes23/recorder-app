"use client";

import { useStudio } from "@/features/studio/model/studio-context";

export const useProduction = () => useStudio().production;
export const useMusic = () => useStudio().music;
