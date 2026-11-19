/** edge-tts es gratis; ElevenLabs gasta créditos de la cuenta del usuario. */
export type VoiceProvider = "edge" | "elevenlabs";

export type Voice = {
  id: string;
  label: string;
  provider: VoiceProvider;
  /** Muestra de audio de la voz, si el proveedor la da. Vacío si no. */
  preview?: string;
};

/** El motor espera el signo explícito: «+8%», «-4Hz». */
export const signed = (value: number): string => `${value >= 0 ? "+" : ""}${value}`;

export const formatRate = (percent: number): string => `${signed(percent)}%`;
export const formatPitch = (hz: number): string => `${signed(hz)}Hz`;

export const voiceLabel = (voices: Voice[], id: string): string | null =>
  voices.find((v) => v.id === id)?.label ?? null;
