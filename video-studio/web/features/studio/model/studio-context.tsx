"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { EventStream, StudioGateway } from "@/application/ports";
import { previewFrame } from "@/application/use-cases/preview-frame";
import { renderVideo } from "@/application/use-cases/render-video";
import { writeScript } from "@/application/use-cases/write-script";
import type { Config } from "@/domain/config";
import type { VideoItem } from "@/domain/library";
import { useBackgroundsSlice, type BackgroundsSlice } from "@/features/backgrounds/model/backgrounds-slice";
import { useCaptionsSlice, type CaptionsSlice } from "@/features/captions/model/captions-slice";
import { useLibrarySlice, type LibrarySlice } from "@/features/library/model/library-slice";
import { useRenderSlice, type RenderSlice } from "@/features/render/model/render-slice";
import { useScenesSlice, type ScenesSlice } from "@/features/scenes/model/scenes-slice";
import { useScriptSlice, type ScriptSlice } from "@/features/script/model/script-slice";
import { useStatusSlice, type StatusSlice } from "@/features/studio/model/status-slice";
import { useVoiceSlice, type VoiceSlice } from "@/features/voice/model/voice-slice";
import { useWriterSlice, type WriterSlice } from "@/features/writer/model/writer-slice";

import type { SliceDeps } from "./deps";
import { useJobTracker } from "./job-tracker";

/**
 * Raíz de composición de la interfaz.
 *
 * Cada feature guarda su propio estado; aquí se juntan y se resuelve lo único
 * que ninguna puede resolver sola: las acciones que necesitan datos de varias
 * (previsualizar, renderizar, reutilizar un video del historial).
 *
 * El gateway entra por parámetro, así que ninguna feature conoce la
 * implementación HTTP y montar el estudio contra un doble de pruebas es
 * cambiar un argumento.
 */

export type StudioActions = {
  /** Redacta el guion con el modelo, o con la plantilla local del motor. */
  write: (useTemplate: boolean) => Promise<void>;
  preview: () => Promise<void>;
  render: () => Promise<void>;
  /** Clona los ajustes de un video ya renderizado. */
  reuse: (item: VideoItem) => void;
};

export type Studio = {
  config: Config | null;
  status: StatusSlice;
  script: ScriptSlice;
  voice: VoiceSlice;
  captions: CaptionsSlice;
  scenes: ScenesSlice;
  backgrounds: BackgroundsSlice;
  library: LibrarySlice;
  render: RenderSlice;
  writer: WriterSlice;
  actions: StudioActions;
};

const StudioContext = createContext<Studio | null>(null);

export function useStudio(): Studio {
  const studio = useContext(StudioContext);
  if (!studio) throw new Error("Falta <StudioProvider> por encima de este componente.");
  return studio;
}

export function StudioProvider({
  gateway,
  events,
  children,
}: {
  gateway: StudioGateway;
  /** Flujo de hechos del servidor: por aquí llegan los trabajos terminados. */
  events: EventStream;
  children: ReactNode;
}) {
  const status = useStatusSlice();
  const { run, setError } = status;
  const jobStatus = useCallback((job: string) => gateway.jobStatus(job), [gateway]);
  const jobs = useJobTracker(events, jobStatus);

  const deps = useMemo<SliceDeps>(() => ({ gateway, run, setError }), [gateway, run, setError]);

  const [config, setConfig] = useState<Config | null>(null);
  const script = useScriptSlice();
  const voice = useVoiceSlice();
  const captions = useCaptionsSlice();
  const scenes = useScenesSlice();
  const backgrounds = useBackgroundsSlice(deps);
  const library = useLibrarySlice(deps);
  const render = useRenderSlice(deps, library.load);
  const writer = useWriterSlice(deps);

  const { setId: selectVoice } = voice;
  const { apply: applyStyle } = captions;
  const { load: loadBackgrounds } = backgrounds;
  const { load: loadLibrary } = library;
  const { load: loadWriter } = writer;

  /* Arranque: el servidor manda con las voces y el estilo por defecto. Los
     ajustes del modelo son secundarios, así que su fallo no tumba la carga. */
  useEffect(() => {
    (async () => {
      try {
        const loaded = await gateway.config();
        setConfig(loaded);
        applyStyle(loaded.defaultStyle);
        if (loaded.voices[0]) selectVoice(loaded.voices[0].id);
        await Promise.all([
          loadBackgrounds(),
          loadLibrary(),
          loadWriter().catch(() => undefined),
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [gateway, applyStyle, selectVoice, loadBackgrounds, loadLibrary, loadWriter, setError]);

  const actions = useMemo<StudioActions>(
    () => ({
      write: async (useTemplate) => {
        const text = await run(useTemplate ? "template" : "writer", () =>
          writeScript(gateway, jobs, { topic: script.topic, notes: script.notes, useTemplate }),
        );
        if (text !== undefined) script.setText(text);
      },

      preview: async () => {
        const frame = await run("preview", () =>
          previewFrame(gateway, {
            script: script.text,
            topic: script.topic,
            scenes: scenes.items,
            style: captions.style,
          }),
        );
        if (frame) render.showPreview(frame);
      },

      render: async () => {
        const id = await run("render", () =>
          renderVideo(gateway, {
            topic: script.topic,
            script: script.text,
            voice: voice.id,
            rate: voice.rate,
            pitch: voice.pitch,
            style: captions.style,
            scenes: scenes.items,
          }),
        );
        if (id === undefined) return;
        render.track(id);
        loadLibrary();
      },

      reuse: (item) => {
        script.setTopic(item.topic);
        script.setText(item.script);
        voice.setId(item.voice);
        scenes.replaceAll(Array.isArray(item.scenes) ? item.scenes : []);
        captions.apply(item.style);
        window.scrollTo({ top: 0, behavior: "smooth" });
      },
    }),
    [gateway, jobs, run, script, voice, captions, scenes, render, loadLibrary],
  );

  const studio = useMemo<Studio>(
    () => ({
      config, status, script, voice, captions, scenes,
      backgrounds, library, render, writer, actions,
    }),
    [config, status, script, voice, captions, scenes, backgrounds, library, render, writer, actions],
  );

  return <StudioContext.Provider value={studio}>{children}</StudioContext.Provider>;
}
