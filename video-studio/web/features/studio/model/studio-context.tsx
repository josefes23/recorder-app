"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type { EventStream, StudioGateway } from "@/application/ports";
import {
  awaitSceneClip,
  requestSceneAnimation,
  type SceneAnimation,
} from "@/application/use-cases/animate-scenes";
import {
  awaitReference,
  repaintReference,
  saveToLibrary,
} from "@/application/use-cases/character-library";
import {
  awaitSceneImage,
  planStoryboard,
  requestSceneCorrection,
  requestSceneImage,
  requestSceneImages,
} from "@/application/use-cases/illustrate-scenes";
import { paintCover, suggestTitles } from "@/application/use-cases/design-cover";
import { previewFrame } from "@/application/use-cases/preview-frame";
import { renderVideo } from "@/application/use-cases/render-video";
import { writeDescription } from "@/application/use-cases/write-description";
import { writeScript } from "@/application/use-cases/write-script";
import { isImageFile } from "@/domain/background";
import type { Config } from "@/domain/config";
import { firstBackground, readCover, resolveCover, type Cover } from "@/domain/cover";
import type { VideoItem } from "@/domain/library";
import { DEFAULT_STYLE, type Style } from "@/domain/captions";
import { assignVoices, speakersIn, type DialogueVoices } from "@/domain/dialogue";
import { HORIZONTAL_CAPTIONS, lengthRange, splitStoredStyle, type FormatId } from "@/domain/production";
import { animatable, buildTimeline, fromStoryboard, withoutBackground, type Scene } from "@/domain/scene";
import { useAnimationSlice, type AnimationSlice } from "@/features/animation/model/animation-slice";
import { useBackgroundsSlice, type BackgroundsSlice } from "@/features/backgrounds/model/backgrounds-slice";
import { useCaptionsSlice, type CaptionsSlice } from "@/features/captions/model/captions-slice";
import { useCoverSlice, type CoverSlice } from "@/features/cover/model/cover-slice";
import { useDescriptionSlice, type DescriptionSlice } from "@/features/description/model/description-slice";
import { useCharactersSlice, type CharactersSlice } from "@/features/illustrations/model/characters-slice";
import { useImagesSlice, type ImagesSlice } from "@/features/illustrations/model/images-slice";
import { useMusicSlice, type MusicSlice } from "@/features/production/model/music-slice";
import { useProductionSlice, type ProductionSlice } from "@/features/production/model/production-slice";
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
  /** Pide corregir la imagen de esa escena contando qué está mal; llega en su lugar. */
  correctScene: (index: number, correction: string) => Promise<boolean>;
  /** Anima la imagen de esa escena (o la original, si ya lleva un clip) con el largo de su tramo. */
  animateScene: (index: number) => Promise<void>;
  /** Anima todas las escenas con imagen que todavía no tienen clip. */
  animateAll: () => Promise<void>;
  /** Guarda en la biblioteca ese elemento del reparto y le encarga su imagen de referencia. */
  saveCharacter: (index: number) => Promise<void>;
  /** Pinta otra imagen de referencia, con el estilo del video abierto. */
  repaintReference: (id: number) => Promise<void>;
  /** Lo borra de la biblioteca; en el reparto del video se queda, sin referencia. */
  deleteSaved: (id: number) => Promise<void>;
  /** Pide al modelo del guion títulos gancho para la portada. */
  suggestTitles: () => Promise<void>;
  /** Pinta una imagen solo para la portada; al llegar, la portada la usa. */
  illustrateCover: (description: string) => Promise<boolean>;
  /** Pide al modelo del guion la descripción para publicar; sustituye a la que hubiera. */
  writeDescription: () => Promise<void>;
  /**
   * Cambia el formato del video. Los subtítulos se acomodan: en horizontal van
   * más abajo, más anchos y en menos líneas.
   */
  chooseFormat: (format: FormatId) => void;
};

/** La portada elegida y la que sale de verdad con el tema y las escenas de ahora. */
export type CoverState = CoverSlice & {
  /** La que se ve, se renderiza y se descarga; null mientras no haya título. */
  resolved: Cover | null;
  /** La imagen que usa si no se elige otra: la de la primera escena con imagen. */
  automatic: string | null;
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
  animation: AnimationSlice;
  production: ProductionSlice;
  music: MusicSlice;
  characters: CharactersSlice;
  cover: CoverState;
  description: DescriptionSlice;
  actions: StudioActions;
};

/** Espera tras el último cambio antes de repintar la portada: no una por tecla. */
const COVER_DEBOUNCE_MS = 450;

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
  const production = useProductionSlice();
  const range = useMemo(() => lengthRange(production.length), [production.length]);
  const script = useScriptSlice(range);
  const voice = useVoiceSlice();
  const captions = useCaptionsSlice();
  const scenes = useScenesSlice();
  const backgrounds = useBackgroundsSlice(deps, production.format);
  const library = useLibrarySlice(deps);
  const render = useRenderSlice(deps, library.load);
  const writer = useWriterSlice(deps);
  const images = useImagesSlice(deps);
  const animation = useAnimationSlice(deps);
  const music = useMusicSlice(deps);
  const characters = useCharactersSlice(deps);
  const coverSlice = useCoverSlice();
  const description = useDescriptionSlice();

  /* La portada que sale de verdad. Depende del nombre de la imagen automática
     y no de la lista de escenas: esa cambia cada vez que una imagen pedida
     avanza, y la portada se repintaría sin motivo. */
  const automaticCover = firstBackground(scenes.items);
  const resolvedCover = useMemo(
    () => resolveCover(coverSlice.draft, script.topic, automaticCover),
    [coverSlice.draft, script.topic, automaticCover],
  );
  const cover = useMemo<CoverState>(
    () => ({ ...coverSlice, resolved: resolvedCover, automatic: automaticCover }),
    [coverSlice, resolvedCover, automaticCover],
  );

  /* Se repinta sola al cambiar título, diseño, imagen o tema, como un espejo.
     Fuera de `run`: es local, tarda medio segundo y no debe bloquear botones. */
  const { begin: beginCover, show: showCover, fail: failCover, clear: clearCover } = coverSlice;
  useEffect(() => {
    if (!resolvedCover) {
      clearCover();
      return;
    }
    const timer = setTimeout(() => {
      const ticket = beginCover();
      paintCover(gateway, { ...resolvedCover, topic: script.topic, format: production.format })
        .then((image) => showCover(ticket, image))
        .catch((err: unknown) => failCover(ticket, err instanceof Error ? err.message : String(err)));
    }, COVER_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [gateway, resolvedCover, script.topic, production.format, beginCover, showCover, failCover, clearCover]);

  const { setId: selectVoice } = voice;
  const { apply: applyStyle } = captions;
  const { load: loadBackgrounds } = backgrounds;
  const { load: loadLibrary } = library;
  const { load: loadWriter } = writer;
  const { load: loadImages, adopt: adoptGuide, setCharacters } = images;
  const { load: loadCharacters, setPainting, setFailure } = characters;
  const { startImage, finishImage, failImage } = scenes;
  const { startClipAt, startClipOn, finishClip, failClip, failClipOn } = scenes;
  const { load: loadAnimation } = animation;
  const { load: loadMusic } = music;

  /* Lo último de la pantalla, para las esperas largas: cuando una imagen llega
     un minuto después, sus callbacks ven el estado de entonces, no el de ahora.
     Se pone al día después de cada render. */
  const latest = useRef({
    scenes: scenes.items as Scene[],
    voice: script.seconds,
    auto: animation.auto,
    topic: script.topic,
    guide: images.guide,
    format: production.format,
  });
  useEffect(() => {
    latest.current = {
      scenes: scenes.items,
      voice: script.seconds,
      auto: animation.auto,
      topic: script.topic,
      guide: images.guide,
      format: production.format,
    };
  });

  /* Con el diálogo activado, cada personaje que aparece en el guion recibe una
     voz distinta de la del narrador; las que ya se eligieron se respetan. */
  const { dialogue, voices: dialogueVoices, setVoices } = production;
  const voiceCatalog = config?.voices;
  useEffect(() => {
    if (!dialogue || !voiceCatalog) return;
    const next = assignVoices(speakersIn(script.text), voiceCatalog, voice.id, dialogueVoices);
    if (!sameVoices(next, dialogueVoices)) setVoices(next);
  }, [dialogue, script.text, voiceCatalog, voice.id, dialogueVoices, setVoices]);

  /* Un clip tarda minutos: se espera fuera de `run`, como las imágenes. */
  const trackClip = useCallback(
    (job: string) => {
      awaitSceneClip(jobs, job)
        .then(async (name) => {
          await loadBackgrounds().catch(() => undefined);
          finishClip(job, name);
        })
        .catch((err: unknown) => failClip(job, err instanceof Error ? err.message : String(err)));
    },
    [jobs, loadBackgrounds, finishClip, failClip],
  );

  /** Pide la animación; `mark` sitúa el trabajo en su escena y `fail` cuenta por qué no se pudo pedir. */
  const animate = useCallback(
    async (scene: SceneAnimation, mark: (job: string) => void, fail: (message: string) => void) => {
      try {
        const { topic, guide, format } = latest.current;
        const job = await requestSceneAnimation(gateway, scene, { topic, guide, format });
        mark(job);
        trackClip(job);
      } catch (err) {
        fail(err instanceof Error ? err.message : String(err));
      }
    },
    [gateway, trackClip],
  );

  /* Una imagen pedida se espera fuera de `run`: tarda, llegan varias a la vez
     y no deben bloquear el resto de botones. Cada escena enseña lo suyo. */
  const trackImage = useCallback(
    (job: string) => {
      awaitSceneImage(jobs, job)
        .then(async ({ name, review }) => {
          // La galería primero: así la escena estrena miniatura y no un hueco.
          await loadBackgrounds().catch(() => undefined);
          // Antes de estrenarla: después ya no se sabe qué escena la esperaba.
          const { scenes: current, voice, auto } = latest.current;
          const index = current.findIndex((scene) => scene.job === job);
          finishImage(job, name, review);

          // Con el interruptor prendido, la imagen nueva se anima sola. Se busca
          // por nombre: entre pedir el clip y que salga, la escena pudo moverse.
          if (auto && index >= 0 && isImageFile(name)) {
            const span = buildTimeline(current, voice).segments[index]?.span ?? 0;
            await animate(
              { source: name, description: current[index].prompt ?? "", span },
              (clipJob) => startClipOn(name, clipJob),
              (message) => failClipOn(name, message),
            );
          }
        })
        .catch((err: unknown) => failImage(job, err instanceof Error ? err.message : String(err)));
    },
    [jobs, loadBackgrounds, finishImage, failImage, animate, startClipOn, failClipOn],
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
          loadAnimation().catch(() => undefined),
          loadMusic().catch(() => undefined),
          loadCharacters().catch(() => undefined),
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [
    gateway, applyStyle, selectVoice, loadBackgrounds, loadLibrary, loadWriter, loadImages,
    loadAnimation, loadMusic, loadCharacters, setError,
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
          writeScript(gateway, jobs, {
            topic: script.topic,
            notes: script.notes,
            useTemplate,
            length: production.length,
            dialogue: production.dialogue,
          }),
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
            format: production.format,
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
            cover: resolvedCover,
            description: description.text,
            production,
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
        // El estilo guardado lleva dentro la producción: se separan.
        const stored = splitStoredStyle(item.style);
        captions.apply(stored.style);
        production.restore(stored.production);
        coverSlice.restore(readCover(item.cover));
        coverSlice.setSuggestions([]);
        description.setText(item.description ?? "");
        window.scrollTo({ top: 0, behavior: "smooth" });
      },

      deleteBackground: async (name) => {
        const items = await backgrounds.remove(name);
        if (items === undefined) return false;
        // Una escena con un fondo que ya no existe haría fallar el render.
        scenes.replaceAll(withoutBackground(scenes.items, name));
        // La portada vuelve a la imagen automática en vez de quedarse sin ninguna.
        if (coverSlice.draft.background === name) coverSlice.setBackground(null);
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
            length: production.length,
            format: production.format,
            topic: script.topic,
            script: script.text,
            style: images.guide.look,
            // Solo lo que está en el reparto: lo guardado entra a mano, nunca solo.
            characters: images.guide.characters,
          }),
        );
        if (!storyboard) return;
        adoptGuide(storyboard.guide);
        scenes.replaceAll(fromStoryboard(storyboard.scenes));
        // Escenas nuevas: la portada estrena la primera imagen que llegue.
        coverSlice.setBackground(null);

        const descriptions = storyboard.scenes.map((scene) => scene.description);
        await run("illustrate", () =>
          requestSceneImages(
            gateway,
            descriptions,
            { ...choice, topic: script.topic, guide: storyboard.guide, review: images.review, format: production.format },
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
            format: production.format,
          }),
        );
        if (!job) return false;
        startImage(index, job, description.trim());
        trackImage(job);
        return true;
      },

      correctScene: async (index, correction) => {
        const { choice } = images;
        const scene = scenes.items[index];
        if (!choice) {
          setError("Configura un generador de imágenes en «Generador de imágenes».");
          return false;
        }
        const source = scene?.background;
        if (!source) return false;
        const description = scene.prompt ?? "";
        const job = await run(`correct-${index}`, () =>
          requestSceneCorrection(
            gateway,
            { source, correction, description },
            { ...choice, topic: script.topic, guide: images.guide, review: images.review, format: production.format },
          ),
        );
        if (!job) return false;
        // La escena conserva lo que debía mostrar: la corregida es la misma escena.
        startImage(index, job, description);
        trackImage(job);
        return true;
      },

      animateScene: async (index) => {
        const scene = scenes.items[index];
        const source = scene ? animatable(scene) : null;
        if (!scene || !source) return;
        const span = buildTimeline(scenes.items, script.seconds).segments[index]?.span ?? 0;
        const current = scene.background ?? source;
        await animate(
          { source, description: scene.prompt ?? "", span },
          (job) => startClipAt(index, job),
          (message) => failClipOn(current, message),
        );
      },

      animateAll: async () => {
        const { segments } = buildTimeline(scenes.items, script.seconds);
        // Solo las que aún no tienen clip: para rehacer una está su botón.
        const pending = scenes.items.flatMap((scene, index) => {
          const source = animatable(scene);
          return source && !scene.still ? [{ scene, index, source }] : [];
        });
        for (const { scene, index, source } of pending) {
          await animate(
            { source, description: scene.prompt ?? "", span: segments[index]?.span ?? 0 },
            (job) => startClipOn(source, job),
            (message) => failClipOn(source, message),
          );
        }
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

      /* Los títulos y la imagen de portada tardan lo que tarde el modelo: se
         esperan fuera de `run` para no bloquear el resto de botones, y cada uno
         enseña su propio «trabajando». */
      suggestTitles: async () => {
        setError(null);
        coverSlice.setSuggesting(true);
        try {
          coverSlice.setSuggestions(
            await suggestTitles(gateway, jobs, { topic: script.topic, script: script.text }),
          );
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          coverSlice.setSuggesting(false);
        }
      },

      illustrateCover: async (description) => {
        const { choice } = images;
        if (!choice) {
          setError("Configura un generador de imágenes en «Generador de imágenes».");
          return false;
        }
        setError(null);
        coverSlice.setIllustrating(true);
        try {
          // Con la guía del video: mismo estilo, mismo reparto y misma semilla que sus escenas.
          const job = await requestSceneImage(gateway, description, {
            ...choice,
            topic: script.topic,
            guide: images.guide,
            review: images.review,
            format: production.format,
          });
          const { name } = await awaitSceneImage(jobs, job);
          await loadBackgrounds().catch(() => undefined);
          coverSlice.setBackground(name);
          return true;
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
          return false;
        } finally {
          coverSlice.setIllustrating(false);
        }
      },

      chooseFormat: (format) => {
        production.setFormat(format);
        // Los subtítulos de cada formato: los horizontales o los del servidor.
        const vertical: Partial<Style> = config?.defaultStyle ?? DEFAULT_STYLE;
        const { font_size, y_ratio, max_lines, max_chars } = vertical;
        captions.apply(format === "16:9" ? HORIZONTAL_CAPTIONS : { font_size, y_ratio, max_lines, max_chars });
      },

      writeDescription: async () => {
        setError(null);
        description.setWriting(true);
        try {
          description.setText(
            await writeDescription(gateway, jobs, {
              topic: script.topic,
              script: script.text,
              title: resolvedCover?.title ?? "",
            }),
          );
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          description.setWriting(false);
        }
      },
    }),
    [
      gateway, jobs, run, setError, script, voice, captions, scenes, backgrounds, render,
      loadLibrary, images, adoptGuide, startImage, trackImage, characters, setCharacters,
      loadCharacters, trackReference, coverSlice, resolvedCover, loadBackgrounds, description,
      animate, startClipAt, startClipOn, failClipOn, production, config,
    ],
  );

  const studio = useMemo<Studio>(
    () => ({
      config, status, script, voice, captions, scenes, backgrounds, library, render, writer,
      images, animation, production, music, characters, cover, description, actions,
    }),
    [
      config, status, script, voice, captions, scenes, backgrounds, library, render, writer, images,
      animation, production, music, characters, cover, description, actions,
    ],
  );

  return <StudioContext.Provider value={studio}>{children}</StudioContext.Provider>;
}

function sameVoices(a: DialogueVoices, b: DialogueVoices): boolean {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => a[key] === b[key]);
}
