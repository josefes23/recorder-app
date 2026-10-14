"use client";

import { useStudio } from "./studio-context";

/** Acciones que necesitan datos de varias features a la vez. */
export const useStudioActions = () => useStudio().actions;

/** Ocupado y error, compartidos por toda la interfaz. */
export const useStatus = () => useStudio().status;
