"use client";

import { useStudio } from "@/features/studio/model/studio-context";

export const useAnimation = () => useStudio().animation;
