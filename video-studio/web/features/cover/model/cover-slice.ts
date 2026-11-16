"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DEFAULT_DESIGN, type Cover, type CoverDesign, type CoverDraft } from "@/domain/cover";

const AUTOMATIC: CoverDraft = { title: null, design: DEFAULT_DESIGN, background: null };

export type CoverSlice = {
  /** Lo elegido; `null` en título o imagen es «automático». */
  draft: CoverDraft;
  setTitle: (title: string) => void;
  setDesign: (design: CoverDesign) => void;
  /** `null` vuelve a la imagen de la primera escena. */
  setBackground: (name: string | null) => void;
  /** La que se guardó con un video, o todo automático si no tenía. */
  restore: (cover: Cover | null) => void;

  /** La portada pintada, a tamaño completo: se ve y se descarga la misma. */
  imageUrl: string | null;
  painting: boolean;
  /** Por qué no se pudo pintar. Va bajo la portada, no en el error general. */
  failure: string | null;
  /**
   * Abre un encargo de pintura y devuelve su número. Solo el último manda:
   * si se escribe rápido, una respuesta vieja que llegue tarde no pisa a la nueva.
   */
  begin: () => number;
  show: (ticket: number, image: Blob) => void;
  fail: (ticket: number, message: string) => void;
  /** Sin título no hay portada que enseñar. */
  clear: () => void;

  suggestions: string[];
  setSuggestions: (titles: string[]) => void;
  suggesting: boolean;
  setSuggesting: (on: boolean) => void;
  /** Hay una imagen pintándose solo para la portada. */
  illustrating: boolean;
  setIllustrating: (on: boolean) => void;
};

export function useCoverSlice(): CoverSlice {
  const [draft, setDraft] = useState<CoverDraft>(AUTOMATIC);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [painting, setPainting] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const [illustrating, setIllustrating] = useState(false);

  const ticketRef = useRef(0);
  const urlRef = useRef<string | null>(null);

  const setTitle = useCallback((title: string) => setDraft((d) => ({ ...d, title })), []);
  const setDesign = useCallback((design: CoverDesign) => setDraft((d) => ({ ...d, design })), []);
  const setBackground = useCallback(
    (background: string | null) => setDraft((d) => ({ ...d, background })),
    [],
  );
  const restore = useCallback((cover: Cover | null) => setDraft(cover ?? AUTOMATIC), []);

  const replaceUrl = useCallback((next: string | null) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = next;
    setImageUrl(next);
  }, []);

  const begin = useCallback(() => {
    ticketRef.current += 1;
    setPainting(true);
    return ticketRef.current;
  }, []);

  const show = useCallback(
    (ticket: number, image: Blob) => {
      if (ticket !== ticketRef.current) return;
      replaceUrl(URL.createObjectURL(image));
      setFailure(null);
      setPainting(false);
    },
    [replaceUrl],
  );

  const fail = useCallback((ticket: number, message: string) => {
    if (ticket !== ticketRef.current) return;
    setFailure(message);
    setPainting(false);
  }, []);

  const clear = useCallback(() => {
    ticketRef.current += 1;
    replaceUrl(null);
    setFailure(null);
    setPainting(false);
  }, [replaceUrl]);

  /* La URL de blob sobrevive al desmontaje si no se revoca. */
  useEffect(
    () => () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  return useMemo(
    () => ({
      draft, setTitle, setDesign, setBackground, restore,
      imageUrl, painting, failure, begin, show, fail, clear,
      suggestions, setSuggestions, suggesting, setSuggesting, illustrating, setIllustrating,
    }),
    [
      draft, setTitle, setDesign, setBackground, restore,
      imageUrl, painting, failure, begin, show, fail, clear,
      suggestions, suggesting, illustrating,
    ],
  );
}
