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
import {
  awaitReference,
  repaintReference,
  saveToLibrary,
} from "@/application/use-cases/character-library";
import {
  awaitSceneImage,
  planStoryboard,
  requestSceneImage,
  requestSceneImages,
} from "@/application/use-cases/illustrate-scenes";
import { previewFrame } from "@/application/use-cases/preview-frame";
import { renderVideo } from "@/application/use-cases/render-video";
import { writeScript } from "@/application/use-cases/write-script";
import type { Config } from "@/domain/config";
import type { VideoItem } from "@/domain/library";
import { fromStoryboard, withoutBackground } from "@/domain/scene";
import { useBackgroundsSlice, type BackgroundsSlice } from "@/features/backgrounds/model/backgrounds-slice";
import { useCaptionsSlice, type CaptionsSlice } from "@/features/captions/model/captions-slice";
import { useCharactersSlice, type CharactersSlice } from "@/features/illustrations/model/characters-slice";
import { useImagesSlice, type ImagesSlice } from "@/features/illustrations/model/images-slice";
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
  /** Borra un fondo de la galería y lo quita de las escenas que lo usaban. */
  deleteBackground: (name: string) => Promise<boolean>;
  /** Rehace las escenas desde el guion: guion visual primero y una imagen por tramo. */
  illustrateAll: () => Promise<void>;
  /** Pide una imagen para esa escena; `null` añade una escena nueva al final. */
  illustrateScene: (index: number | null, description: string) => Promise<boolean>;
  /** Guarda en la biblioteca ese elemento del reparto y le encarga su imagen de referencia. */
  saveCharacter: (index: number) => Promise<void>;
  /** Pinta otra imagen de referencia, con el estilo del video abierto. */
  repaintReference: (id: number) => Promise<void>;
  /** Lo borra de la biblioteca; en el reparto del video se queda, sin referencia. */
  deleteSaved: (id: number) => Promise<void>;
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
  images: ImagesSlice;
  characters: CharactersSlice;
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
  const images = useImagesSlice(deps);
  const characters = useCharactersSlice(deps);

  const { setId: selectVoice } = voice;
  const { apply: applyStyle } = captions;
  const { load: loadBackgrounds } = backgrounds;
  const { load: loadLibrary } = library;
  const { load: loadWriter } = writer;
  const { load: loadImages, adopt: adoptGuide, setCharacters } = images;
  const { load: loadCharacters, setPainting, setFailure } = characters;
  const { startImage, finishImage, failImage } = scenes;

  /* Una imagen pedida se espera fuera de `run`: tarda, llegan varias a la vez
     y no deben bloquear el resto de botones. Cada escena enseña lo suyo. */
  const trackImage = useCallback(
    (job: string) => {
      awaitSceneImage(jobs, job)
        .then(async ({ name, review }) => {
          // La galería primero: así la escena estrena miniatura y no un hueco.
          await loadBackgrounds().catch(() => undefined);
          finishImage(job, name, review);
        })
        .catch((err: unknown) => failImage(job, err instanceof Error ? err.message : String(err)));
    },
    [jobs, loadBackgrounds, finishImage, failImage],
  );

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
          loadImages().catch(() => undefined),
          loadCharacters().catch(() => undefined),
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [
    gateway, applyStyle, selectVoice, loadBackgrounds, loadLibrary, loadWriter, loadImages,
    loadCharacters, setError,
  ]);

  /* La imagen de referencia tarda como cualquier imagen: se espera fuera de
     `run` y la biblioteca se recarga al llegar. */
  const trackReference = useCallback(
    (id: number, job: string) => {
      setPainting(id, true);
      setFailure(id, null);
      awaitReference(jobs, job)
        .then(() => loadCharacters())
        .catch((err: unknown) => setFailure(id, err instanceof Error ? err.message : String(err)))
        .finally(() => setPainting(id, false));
    },
    [jobs, loadCharacters, setPainting, setFailure],
  );

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

      deleteBackground: async (name) => {
        const items = await backgrounds.remove(name);
        if (items === undefined) return false;
        // Una escena con un fondo que ya no existe haría fallar el render.
        scenes.replaceAll(withoutBackground(scenes.items, name));
        return true;
      },

      illustrateAll: async () => {
        const { choice } = images;
        if (!choice) {
          setError("Configura un generador de imágenes en «Generador de imágenes».");
          return;
        }
        /* Primero el guion visual: qué se ve en cada escena, quién sale y con
           qué estilo. Las escenas aparecen ya con su descripción, así que si
           luego falla algún encargo se puede repetir uno a uno. */
        const storyboard = await run("storyboard", () =>
          planStoryboard(gateway, jobs, {
            topic: script.topic,
            script: script.text,
            style: images.guide.look,
            // Lo que el usuario ya puso entra entero; de la biblioteca, lo que encaje.
            characters: images.guide.characters,
          }),
        );
        if (!storyboard) return;
        adoptGuide(storyboard.guide);
        scenes.replaceAll(fromStoryboard(storyboard.scenes));

        const descriptions = storyboard.scenes.map((scene) => scene.description);
        await run("illustrate", () =>
          requestSceneImages(
            gateway,
            descriptions,
            { ...choice, topic: script.topic, guide: storyboard.guide, review: images.review },
            (index, job) => {
              startImage(index, job, descriptions[index]);
              trackImage(job);
            },
          ),
        );
      },

      illustrateScene: async (index, description) => {
        const { choice } = images;
        if (!choice) {
          setError("Configura un generador de imágenes en «Generador de imágenes».");
          return false;
        }
        const job = await run(`illustrate-${index ?? "new"}`, () =>
          requestSceneImage(gateway, description, {
            ...choice,
            topic: script.topic,
            guide: images.guide,
            review: images.review,
          }),
        );
        if (!job) return false;
        startImage(index, job, description.trim());
        trackImage(job);
        return true;
      },

      saveCharacter: async (index) => {
        const character = images.guide.characters[index];
        if (!character) return;
        const result = await run(`save-character-${index}`, () =>
          saveToLibrary(gateway, character, images.guide.look, images.choice),
        );
        if (!result) return;
        const { character: saved, job } = result;
        // Desde ahora sus escenas llevan su imagen de referencia.
        setCharacters((cast) =>
          cast.map((c, i) => (i === index ? { ...c, name: saved.name, saved: saved.id } : c)),
        );
        await loadCharacters().catch(() => undefined);
        if (job) trackReference(saved.id, job);
      },

      repaintReference: async (id) => {
        const job = await run(`reference-${id}`, () =>
          repaintReference(gateway, id, images.guide.look, images.choice),
        );
        if (job) trackReference(id, job);
      },

      deleteSaved: async (id) => {
        if (!(await characters.remove(id))) return;
        setCharacters((cast) => cast.map((c) => (c.saved === id ? { ...c, saved: null } : c)));
      },
    }),
    [
      gateway, jobs, run, setError, script, voice, captions, scenes, backgrounds, render,
      loadLibrary, images, adoptGuide, startImage, trackImage, characters, setCharacters,
      loadCharacters, trackReference,
    ],
  );

  const studio = useMemo<Studio>(
    () => ({
      config, status, script, voice, captions, scenes,
      backgrounds, library, render, writer, images, characters, actions,
    }),
    [
      config, status, script, voice, captions, scenes, backgrounds, library, render, writer, images,
      characters, actions,
    ],
  );

  return <StudioContext.Provider value={studio}>{children}</StudioContext.Provider>;
}
