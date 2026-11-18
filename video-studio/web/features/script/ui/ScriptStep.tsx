"use client";

import { useState, type ReactNode } from "react";

import {
  customLength,
  customSeconds,
  FORMATS,
  LENGTHS,
  MAX_CUSTOM_SECONDS,
  MIN_CUSTOM_SECONDS,
  type FormatId,
  type LengthId,
} from "@/domain/production";
import { useAdvice } from "@/features/growth/model/use-advice";
import { useGrowth } from "@/features/growth/model/use-growth";
import { useProduction } from "@/features/production/model/use-production";
import { useScript } from "@/features/script/model/use-script";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";
import { Field } from "@/shared/ui/Field";
import { Step } from "@/shared/ui/Step";

type Advice = { short: string; long: string; measure: string };

const ADVICE: Record<"reel" | "corto", Advice> = {
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

const CUSTOM = "custom";

/** «90 s», «2 min» o «1 min 30 s». */
function spoken(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
}

function adviceFor(length: LengthId): Advice {
  const seconds = customSeconds(length);
  if (seconds === null) return ADVICE[length as "reel" | "corto"] ?? ADVICE.reel;
  return {
    short: `Se queda corto para ${spoken(seconds)}. Alarga el guion.`,
    long: `Se pasa de ${spoken(seconds)}. Recorta el guion.`,
    measure: `apunta a ${spoken(seconds)}`,
  };
}

/** Duración a medida: una cantidad y su unidad (segundos o minutos). */
function CustomDuration({ seconds, onChange }: { seconds: number; onChange: (length: LengthId) => void }) {
  const [unit, setUnit] = useState<"s" | "min">(seconds >= 60 && seconds % 60 === 0 ? "min" : "s");
  const factor = unit === "min" ? 60 : 1;
  /* Se escribe sin que el límite estorbe (un «9» camino del «90» no salta a 20):
     se confirma, ajustado, al salir del campo o con Enter. */
  const [draft, setDraft] = useState<string | null>(null);

  const commit = (nextUnit: "s" | "min" = unit) => {
    const amount = Number(draft);
    setDraft(null);
    if (draft !== null && Number.isFinite(amount) && amount > 0) {
      onChange(customLength(amount * (nextUnit === "min" ? 60 : 1)));
    }
  };

  return (
    <div className="cluster">
      <input
        id="length-amount"
        type="number"
        inputMode="decimal"
        aria-label="Cantidad"
        min={Math.ceil(MIN_CUSTOM_SECONDS / factor)}
        max={MAX_CUSTOM_SECONDS / factor}
        step={unit === "min" ? 0.5 : 1}
        value={draft ?? String(seconds / factor)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => commit()}
        onKeyDown={(e) => e.key === "Enter" && commit()}
      />
      <select
        aria-label="Unidad"
        value={unit}
        onChange={(e) => {
          setUnit(e.target.value as "s" | "min");
          setDraft(null);
        }}
      >
        <option value="s">segundos</option>
        <option value="min">minutos</option>
      </select>
    </div>
  );
}

/** `settings` es el hueco donde la ruta encaja los ajustes del modelo. */
export function ScriptStep({ settings }: { settings?: ReactNode }) {
  const script = useScript();
  const { busy } = useStatus();
  const actions = useStudioActions();
  const { label } = useWriter();
  const production = useProduction();
  const growth = useGrowth();
  const advise = useAdvice();
  const tips = adviceFor(production.length);
  const custom = customSeconds(production.length);

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
            value={custom === null ? production.length : CUSTOM}
            onChange={(e) =>
              production.setLength(e.target.value === CUSTOM ? customLength(60) : (e.target.value as LengthId))
            }
          >
            {LENGTHS.map((l) => (
              <option key={l.id} value={l.id}>
                {l.label}
              </option>
            ))}
            <option value={CUSTOM}>Personalizada…</option>
          </select>
        </Field>
        {custom !== null && (
          <Field id="length-amount" label="Cuánto dura">
            <CustomDuration seconds={custom} onChange={production.setLength} />
          </Field>
        )}
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
        <button
          className="btn"
          disabled={busy !== null || growth.pending.has("hooks") || !label || (!script.topic.trim() && !script.text.trim())}
          onClick={() => void advise("hooks")}
          title="Cinco ganchos para los primeros tres segundos"
        >
          {growth.pending.has("hooks") ? "Pensando…" : "Ganchos"}
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
