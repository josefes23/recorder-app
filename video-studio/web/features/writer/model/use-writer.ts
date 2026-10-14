"use client";

import { useStudio } from "@/features/studio/model/studio-context";

export const useWriter = () => useStudio().writer;
