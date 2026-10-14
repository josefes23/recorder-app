export type Voice = { id: string; label: string };

/** El motor espera el signo explícito: «+8%», «-4Hz». */
export const signed = (value: number): string => `${value >= 0 ? "+" : ""}${value}`;

export const formatRate = (percent: number): string => `${signed(percent)}%`;
export const formatPitch = (hz: number): string => `${signed(hz)}Hz`;

export const voiceLabel = (voices: Voice[], id: string): string | null =>
  voices.find((v) => v.id === id)?.label ?? null;
