"use client";

import type { ReactNode } from "react";

import { useScript } from "@/features/script/model/use-script";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { useWriter } from "@/features/writer/model/use-writer";
import { Step } from "@/shared/ui/Step";

const ADVICE = {
  short: "Se queda corto para un Reel. Alarga hasta unos treinta segundos.",
  long: "Se pasa de largo. Recorta hasta unos cuarenta y cinco segundos.",
} as const;

/** `settings` es el hueco donde la ruta encaja los ajustes del modelo. */
export function ScriptStep({ settings }: { settings?: ReactNode }) {
  const script = useScript();
  const { busy } = useStatus();
  const actions = useStudioActions();
  const { label } = useWriter();

  const advice = script.verdict === "short" || script.verdict === "long" ? ADVICE[script.verdict] : null;

  return (
    <Step
      n={1}
      title="Guion"
      note={
        script.words > 0 ? (
          <>
            <b className="num">{script.words}</b> palabras ·{" "}
            <b className="num">{script.seconds.toFixed(0)}</b> s
          </>
        ) : (
          "30–45 s es la medida"
        )
      }
    >
      <div className="field">
        <label htmlFor="topic">
          <span>Tema</span>
        </label>
        <input
          id="topic"
          value={script.topic}
          onChange={(e) => script.setTopic(e.target.value)}
          placeholder="Los tres hábitos que arruinan tu sueño"
          autoComplete="off"
        />
      </div>

      <div className="field">
        <label htmlFor="notes">
          <span>Indicaciones</span>
          <span className="hint">opcional</span>
        </label>
        <input
          id="notes"
          value={script.notes}
          onChange={(e) => script.setNotes(e.target.value)}
          placeholder="tono directo, para gente que madruga"
          autoComplete="off"
        />
      </div>

      <div className="cluster">
        <button
          className="btn btn--primary"
          disabled={!label || busy !== null}
          onClick={() => actions.write(false)}
          title={label ? "" : "Añade una clave de API en «Modelo del guion»"}
        >
          {busy === "writer" ? "Escribiendo…" : "Escribir guion"}
        </button>
        <button className="btn" disabled={busy !== null} onClick={() => actions.write(true)}>
          {busy === "template" ? "…" : "Usar plantilla"}
        </button>
        {busy === "writer" && (
          <span className="hint">
            El modelo tarda un minuto largo. El guion aparecerá solo cuando esté.
          </span>
        )}
      </div>

      <div className="field">
        <label htmlFor="script">
          <span>Texto a narrar</span>
          <span className="hint">edítalo antes de renderizar</span>
        </label>
        <textarea
          id="script"
          rows={8}
          value={script.text}
          onChange={(e) => script.setText(e.target.value)}
          placeholder="Escribe o pega aquí el guion…"
        />
        {/* Solo se avisa cuando hay algo que corregir: sin aviso, todo va bien */}
        {advice && <p className="hint warn">{advice}</p>}
      </div>

      {settings}
    </Step>
  );
}
