"use client";

import { useEffect, useRef, useState } from "react";

import { pendingClips, pendingImages } from "@/domain/scene";
import { useLibrary } from "@/features/library/model/use-library";
import { useRender } from "@/features/render/model/use-render";
import { useScenes } from "@/features/scenes/model/use-scenes";
import { stepAnchor, useSteps } from "@/shared/ui/steps";

type Toast = { id: number; text: string; tone: "ok" | "err"; link?: { href: string; label: string; download?: boolean } };

/** Lo que dura un aviso a la vista antes de irse solo. */
const TOAST_MS = 8000;

/**
 * Lo que está trabajando en segundo plano —el render, las imágenes, las
 * animaciones—, siempre a la vista en una esquina, y un aviso cuando termina.
 * Con la pestaña en segundo plano, el título de la página lo cuenta también.
 */
export function JobsTray() {
  const render = useRender();
  const scenes = useScenes();
  const library = useLibrary();
  const steps = useSteps();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const images = pendingImages(scenes.items);
  const clips = pendingClips(scenes.items);
  const job = render.job;
  const progress = Math.round((job?.progress ?? 0) * 100);

  const notify = (toast: Omit<Toast, "id">) => {
    const id = ++counter.current;
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), TOAST_MS);
  };

  /* Avisos al terminar: se compara con lo que había en la vuelta anterior. */
  const before = useRef({ rendering: false, images: 0, clips: 0 });
  useEffect(() => {
    const prev = before.current;
    if (prev.rendering && !render.rendering && job) {
      if (job.status === "done") {
        notify({ text: "Video listo", tone: "ok", link: { href: library.videoUrl(job.id), label: "Descargar", download: true } });
      } else if (job.status === "error") {
        notify({ text: `El render falló${job.error ? `: ${job.error}` : ""}`, tone: "err" });
      }
    }
    if (prev.images > 0 && images === 0) notify({ text: "Llegaron las imágenes de las escenas", tone: "ok" });
    if (prev.clips > 0 && clips === 0) notify({ text: "Terminaron las animaciones", tone: "ok" });
    before.current = { rendering: render.rendering, images, clips };
  }, [render.rendering, job, images, clips, library]);

  /* El título de la pestaña: el progreso del render, y «listo» si se terminó sin mirarla. */
  const original = useRef<string | null>(null);
  useEffect(() => {
    original.current ??= document.title;
    const base = original.current;
    if (render.rendering) {
      document.title = `${progress} % · ${base}`;
      return;
    }
    if (job?.status === "done" && document.hidden) {
      document.title = `✓ Video listo · ${base}`;
      const back = () => {
        if (!document.hidden) document.title = base;
      };
      document.addEventListener("visibilitychange", back);
      return () => document.removeEventListener("visibilitychange", back);
    }
    document.title = base;
  }, [render.rendering, progress, job?.status]);

  const goTo = (id: string, step?: number) => {
    if (step) steps?.unfold(step);
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  const busy = render.rendering || images > 0 || clips > 0;

  return (
    <div className="tray" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast is-${toast.tone}`} role={toast.tone === "err" ? "alert" : "status"}>
          <span>{toast.text}</span>
          {toast.link && (
            <a className="btn btn--sm" href={toast.link.href} download={toast.link.download}>
              {toast.link.label}
            </a>
          )}
          <button
            type="button"
            className="btn--icon"
            aria-label="Cerrar el aviso"
            onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
          >
            ×
          </button>
        </div>
      ))}
      {busy && (
        <div className="jobs" aria-label="Trabajos en curso">
          <p className="panel-title">En curso</p>
          {render.rendering && (
            <button type="button" className="job" onClick={() => goTo("salida")}>
              <span>Render</span>
              <span className="num">{progress} %</span>
              <span className="job-bar">
                <span style={{ width: `${Math.max(progress, 2)}%` }} />
              </span>
            </button>
          )}
          {images > 0 && (
            <button type="button" className="job" onClick={() => goTo(stepAnchor(5), 5)}>
              <span>Imágenes</span>
              <span className="num">{images}</span>
            </button>
          )}
          {clips > 0 && (
            <button type="button" className="job" onClick={() => goTo(stepAnchor(5), 5)}>
              <span>Animaciones</span>
              <span className="num">{clips}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
