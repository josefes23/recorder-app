"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { spokenAt } from "@/domain/narration";
import { wordsAt } from "@/domain/script";
import { DEFAULT_TRANSITION, look, moment, planChanges } from "@/domain/transition";
import { useCurrentTake } from "@/features/narration/model/use-take";
import { useProduction } from "@/features/production/model/use-production";
import { useNarration, useSceneMedia, useScenes } from "@/features/scenes/model/use-scenes";
import { useScript } from "@/features/script/model/use-script";

/** El acercamiento lento de las imágenes fijas, como en el render (`domain/motion.py`). */
const ZOOM_PER_SECOND = 0.02;

const clock = (t: number) => `${t.toLocaleString("es", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;

/**
 * El video en borrador: las imágenes pasan con sus transiciones y abajo la
 * frase que suena. Sin toma de voz, al ritmo estimado y en silencio. Con ella
 * —se genera en unos segundos y es gratis—, con la voz de verdad: cada imagen
 * entra en el segundo en que lo hará en el render, porque el render usa esa
 * misma toma.
 */
export function Animatic() {
  const scenes = useScenes();
  const script = useScript();
  const media = useSceneMedia();
  const narration = useNarration();
  const voice = useCurrentTake();
  const { transition: fallback, format } = useProduction();
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  const total = Math.max(narration.total, 1);
  const withVoice = voice.take !== null;

  /* Como el render: las escenas sin fondo no salen y cada una dura hasta la
     siguiente. Los segundos son los de la voz si hay toma. */
  const plan = useMemo(() => {
    const usable = scenes.items
      .map((scene, i) => ({ scene, n: i + 1, start: i === 0 ? 0 : narration.scenes[i]?.start ?? scene.start }))
      .filter(({ scene }) => scene.background)
      .sort((a, b) => a.start - b.start)
      .filter(({ start }, i) => i === 0 || start < total);
    const bounds = [...usable.map(({ start }, i) => (i === 0 ? 0 : start)), total];
    const changes = planChanges(
      bounds,
      usable.slice(1).map(({ scene }) => scene.transition ?? fallback ?? DEFAULT_TRANSITION),
    );
    const shots = usable.map(({ scene, n }, i) => {
      const { meta, full } = media(scene.background);
      // `n`: el número que lleva en la lista, aunque alguna de antes no salga.
      return { src: full, start: bounds[i], still: meta?.kind !== "video", n };
    });
    return { shots, changes };
  }, [scenes.items, narration.scenes, fallback, total, media]);

  // Las imágenes se cargan antes de que toque verlas: si no, cada cambio parpadea.
  useEffect(() => {
    for (const shot of plan.shots) {
      if (shot.src) new Image().src = shot.src;
    }
  }, [plan.shots]);

  /* El reloj: con voz lo marca el audio (así imagen y voz no se separan);
     sin ella, el reloj del navegador. */
  const playingFrom = useRef<{ wall: number; t: number } | null>(null);
  useEffect(() => {
    if (!playing) return;
    const player = audio.current;
    let frame = 0;
    const tick = (now: number) => {
      let next: number;
      if (player && voice.audioUrl) {
        next = player.currentTime;
        if (player.ended) {
          setT(total);
          setPlaying(false);
          return;
        }
      } else {
        playingFrom.current ??= { wall: now, t };
        next = playingFrom.current.t + (now - playingFrom.current.wall) / 1000;
        if (next >= total) {
          setT(total);
          setPlaying(false);
          return;
        }
      }
      setT(next);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      playingFrom.current = null;
    };
    // `t` solo vale como punto de partida al darle a reproducir.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, total, voice.audioUrl]);

  // Si la toma cambia o deja de valer (otro guion, otra voz), se para.
  const [heard, setHeard] = useState(voice.audioUrl);
  if (heard !== voice.audioUrl) {
    setHeard(voice.audioUrl);
    setPlaying(false);
  }

  const toggle = () => {
    const player = audio.current;
    if (playing) {
      player?.pause();
      setPlaying(false);
      return;
    }
    const from = t >= total ? 0 : t;
    setT(from);
    if (player && voice.audioUrl) {
      player.currentTime = from;
      void player.play().catch(() => setPlaying(false));
    }
    setPlaying(true);
  };

  const seek = (value: number) => {
    audio.current?.pause();
    setPlaying(false);
    setT(value);
    if (audio.current && voice.audioUrl) audio.current.currentTime = value;
  };

  const { shots, changes } = plan;
  const now = moment(changes, t);
  const shot = shots[now.index];
  const next = now.progress !== null ? shots[now.index + 1] : undefined;
  const l = look(now.kind, now.progress ?? 0);
  const drift = (s: typeof shot) => (s?.still ? 1 + ZOOM_PER_SECOND * Math.max(t - s.start, 0) : 1);
  const push = l.push ?? 0;
  const caption = voice.take ? spokenAt(voice.take.words, t) : wordsAt(script.text, t);

  return (
    <div className="stack">
      <div className={`frame animatic${format === "16:9" ? " frame--wide" : ""}`}>
        {shots.length === 0 ? (
          <p className="frame-empty">Añade escenas en el paso 7 para ver cómo pasan con la voz.</p>
        ) : (
          <>
            {shot?.src && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={shot.src}
                alt=""
                style={{
                  transform: `translateX(${-push * 100}%) scale(${drift(shot) * l.zoomOut})`,
                  filter: l.gainOut < 1 ? `brightness(${l.gainOut})` : undefined,
                }}
              />
            )}
            {next?.src && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={next.src}
                alt=""
                style={{
                  transform: `translateX(${l.push === null ? 0 : (1 - push) * 100}%) scale(${drift(next) * l.zoomIn})`,
                  filter: l.gainIn < 1 ? `brightness(${l.gainIn})` : undefined,
                  opacity: l.push === null ? l.alpha : 1,
                }}
              />
            )}
            {caption && <p className="animatic-caption">{caption}</p>}
          </>
        )}
      </div>

      {voice.audioUrl && <audio ref={audio} src={voice.audioUrl} preload="auto" />}

      <div className="cluster animatic-controls">
        <button type="button" className="btn btn--sm" disabled={shots.length === 0} onClick={toggle}>
          {playing ? "Pausa" : t >= total ? "Otra vez" : withVoice ? "Reproducir con voz" : "Reproducir"}
        </button>
        <input
          type="range"
          className="animatic-scrub"
          min={0}
          max={total}
          step={0.1}
          value={Math.min(t, total)}
          aria-label="Segundo de la animática"
          aria-valuetext={clock(t)}
          onChange={(e) => seek(parseFloat(e.target.value))}
        />
        <span className="hint num">
          {clock(Math.min(t, total))} / {clock(total)}
        </span>
      </div>

      {withVoice ? (
        <p className="hint">
          {shot ? `Escena ${shot.n} · ` : ""}
          {voice.audioUrl
            ? "Con la voz de verdad: cada imagen entra en el segundo en que lo hará en el render."
            : "Tiempos de la voz con que se renderizó. Su audio ya no está guardado: genera la voz para oírla."}
        </p>
      ) : (
        <p className="hint">
          {shot ? `Escena ${shot.n} · ` : ""}
          {voice.stale
            ? "Cambiaste el guion o la voz desde la última toma: este es el ritmo estimado."
            : "Ritmo estimado, sin voz."}
        </p>
      )}

      {(!withVoice || !voice.audioUrl) && (
        <button
          type="button"
          className="btn btn--block"
          disabled={voice.generating || !script.text.trim()}
          onClick={() => void voice.generate()}
          title="Genera solo la voz (gratis, unos segundos). El render usará esta misma."
        >
          {voice.generating ? "Generando la voz…" : voice.stale ? "Generar la voz de nuevo" : "Escuchar con la voz"}
        </button>
      )}
      {voice.error && (
        <p className="error" role="alert">
          {voice.error}
        </p>
      )}
    </div>
  );
}
