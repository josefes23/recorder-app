"use client";

import type { ReactNode } from "react";

import { FORMATS, LENGTHS, type FormatId, type LengthId } from "@/domain/production";
import { useProduction } from "@/features/production/model/use-production";
import { useScript } from "@/features/script/model/use-script";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";
import { Field } from "@/shared/ui/Field";
import { Step } from "@/shared/ui/Step";

const ADVICE: Record<LengthId, { short: string; long: string; measure: string }> = {
  reel: {
    short: "Se queda corto para un Reel. Alarga hasta unos treinta segundos.",
    long: "Se pasa de largo. Recorta hasta unos cuarenta y cinco segundos.",
    measure: "30–45 s es la medida",
  },
  corto: {
    short: "Se queda corto para un cortometraje: apunta a dos minutos o más.",
    long: "Pasa de cinco minutos. Recorta un poco o divídelo en dos videos.",
    measure: "de 2 a 5 minutos",
  },
};

/** `settings` es el hueco donde la ruta encaja los ajustes del modelo. */
export function ScriptStep({ settings }: { settings?: ReactNode }) {
  const script = useScript();
  const { busy } = useStatus();
  const actions = useStudioActions();
  const { label } = useWriter();
  const production = useProduction();
  const tips = ADVICE[production.length];

  const advice = script.verdict === "short" || script.verdict === "long" ? tips[script.verdict] : null;

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
          tips.measure
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

      <div className="fields">
        <Field id="format" label="Formato">
          <select
            id="format"
            value={production.format}
            onChange={(e) => actions.chooseFormat(e.target.value as FormatId)}
          >
            {FORMATS.map((f) => (
              <option key={f.id} value={f.id}>
                {f.label} · {f.hint}
              </option>
            ))}
          </select>
        </Field>
        <Field id="length" label="Duración">
          <select
            id="length"
            value={production.length}
            onChange={(e) => production.setLength(e.target.value as LengthId)}
          >
            {LENGTHS.map((l) => (
              <option key={l.id} value={l.id}>
                {l.label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <label className="cluster check" htmlFor="dialogue">
        <input
          id="dialogue"
          type="checkbox"
          checked={production.dialogue}
          onChange={(e) => production.setDialogue(e.target.checked)}
        />
        <span className="hint">
          Guion con diálogos: cada personaje habla con su voz. Una intervención por línea, con el
          nombre en mayúsculas — «ANA: ¿Viste eso?» —; lo demás lo dice el narrador.
        </span>
      </label>

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
      <ActionError place="script" />

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
