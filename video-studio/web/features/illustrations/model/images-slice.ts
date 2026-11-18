"use client";

import { useCallback, useMemo, useState, type Dispatch, type SetStateAction } from "react";

import { configureImages } from "@/application/use-cases/configure-images";
import {
  defaultChoice,
  isAvailable,
  type Character,
  type ImageChoice,
  type ImageSettings,
  type ImageSettingsDraft,
  type VisualGuide,
} from "@/domain/illustration";
import type { SliceDeps } from "@/features/studio/model/deps";

export type ImagesSlice = {
  settings: ImageSettings | null;
  /** Generador y modelo por defecto, o null si ninguno tiene sus datos. */
  label: string | null;
  /** Con qué se pintan las imágenes ahora mismo, o null si no hay generador listo. */
  choice: ImageChoice | null;
  choose: (choice: ImageChoice) => void;
  /**
   * Estilo, reparto y semilla comunes a las escenas de este video, para que
   * casen entre sí. Lo propone el guion visual y el usuario lo retoca.
   */
  guide: VisualGuide;
  setLook: (look: string) => void;
  /** Admite una función, para poner al día el reparto tras una espera sin pisar lo que cambió mientras. */
  setCharacters: Dispatch<SetStateAction<Character[]>>;
  /** Toma la guía que trae un guion visual nuevo, semilla incluida. */
  adopt: (guide: VisualGuide) => void;
  /** Un video en blanco: el estilo del servidor, sin reparto y sin semilla. */
  reset: () => void;
  /**
   * Que el modelo del guion revise cada imagen —manos de más, cuerpos
   * fundidos, letras— y repinte las que tengan fallos. Activado de serie.
   */
  review: boolean;
  setReview: (review: boolean) => void;
  /** Generador abierto en el panel de ajustes; null = el que diga el servidor. */
  editing: string | null;
  edit: (provider: string | null) => void;
  load: () => Promise<void>;
  save: (draft: ImageSettingsDraft) => Promise<boolean>;
};

export function useImagesSlice({ gateway, run }: SliceDeps): ImagesSlice {
  const [settings, setSettings] = useState<ImageSettings | null>(null);
  /* null = «lo que diga el servidor». Una elección que deja de valer —se
     borró una clave, se cambió de generador— cae sola al valor por defecto. */
  const [picked, setPicked] = useState<ImageChoice | null>(null);
  /* null = el estilo por defecto del servidor, hasta que alguien escriba otro. */
  const [typedLook, setLook] = useState<string | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [seed, setSeed] = useState<number | null>(null);
  const [review, setReview] = useState(true);
  const [editing, edit] = useState<string | null>(null);

  const load = useCallback(async () => {
    setSettings(await gateway.imageSettings());
  }, [gateway]);

  const save = useCallback(
    async (draft: ImageSettingsDraft) => {
      if (!settings) return false;
      const saved = await run("images", () => configureImages(gateway, settings, draft));
      if (!saved) return false;
      setSettings(saved);
      setPicked(null); // lo recién guardado pasa a ser el valor por defecto
      edit(null); // y el panel vuelve a reflejar lo guardado
      return true;
    },
    [gateway, run, settings],
  );

  const choice = useMemo(
    () => (isAvailable(settings, picked) ? picked : defaultChoice(settings)),
    [settings, picked],
  );
  const look = typedLook ?? settings?.style ?? "";
  const guide = useMemo(() => ({ look, characters, seed }), [look, characters, seed]);

  const adopt = useCallback((next: VisualGuide) => {
    setLook(next.look);
    setCharacters(next.characters);
    setSeed(next.seed);
  }, []);

  const reset = useCallback(() => {
    setLook(null);
    setCharacters([]);
    setSeed(null);
  }, []);

  return useMemo(
    () => ({
      settings,
      label: settings?.label ?? null,
      choice,
      choose: setPicked,
      guide,
      setLook,
      setCharacters,
      adopt,
      reset,
      review,
      setReview,
      editing,
      edit,
      load,
      save,
    }),
    [settings, choice, guide, adopt, reset, review, editing, load, save],
  );
}
