"use client";

import { useStudio } from "@/features/studio/model/studio-context";

export const useGrowth = () => useStudio().growth;
