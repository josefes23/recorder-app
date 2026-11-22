"use client";

import { useState } from "react";

import {
  REGENERATION_LABELS,
  fixAllInstruction,
  scoreTone,
  type GrowthKind,
  type GrowthResults,
} from "@/domain/growth";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { CopyButton } from "@/shared/ui/CopyButton";
import { useConfirm } from "@/shared/ui/confirm";

export function ScoreBadge({
  score,
  label,
}: {
  score: number;
  label?: string;
}) {
  return (
    <span
      className={`growth-score is-${scoreTone(score)}`}
      title={label ? `${label}: ${score} de 100` : `${score} de 100`}
    >
      <b className="num">{score}</b>
      <span className="visually-hidden"> de 100</span>
    </span>
  );
}

type Actions = {
  applyHook: (hook: string) => void;
  applySeo: (text: string) => void;
  useTopic: (topic: string) => void;
};

/** Lo que dijo el modelo de cada consejo, listo para leer y para aplicar. */
export function GrowthResult<K extends GrowthKind>({
  kind,
  result,
  actions,
  appliedHook,
}: {
  kind: K;
  result: GrowthResults[K];
  actions: Actions;
  appliedHook: string | null;
}) {
  switch (kind) {
    case "hooks": {
      const { hooks } = result as GrowthResults["hooks"];
      return (
        <ol className="growth-list">
          {hooks.map((hook) => (
            <li key={hook.text} className="growth-item">
              <p className="growth-main">
                {hook.type && <span className="chip">{hook.type}</span>}{" "}
                {hook.text}
              </p>
              {hook.why && <p className="hint">{hook.why}</p>}
              <div className="cluster">
                <button
                  className="btn btn--sm"
                  onClick={() => actions.applyHook(hook.text)}
                  disabled={appliedHook === hook.text}
                  title="Lo pone al principio del guion; si ya pusiste otro gancho, lo sustituye"
                >
                  {appliedHook === hook.text
                    ? "En el guion"
                    : "Usar como primera frase"}
                </button>
                <CopyButton
                  text={hook.text}
                  label="Copiar"
                  className="btn btn--sm"
                />
              </div>
            </li>
          ))}
        </ol>
      );
    }
    case "titles": {
      const { titles } = result as GrowthResults["titles"];
      return (
        <ol className="growth-list">
          {titles.map((title) => (
            <li key={title.text} className="growth-item">
              <p className="growth-main">
                <ScoreBadge score={title.score} /> {title.text}
              </p>
              {title.why && <p className="hint">{title.why}</p>}
              <div className="cluster">
                <CopyButton
                  text={title.text}
                  label="Copiar"
                  className="btn btn--sm"
                />
              </div>
            </li>
          ))}
        </ol>
      );
    }
    case "seo": {
      const r = result as GrowthResults["seo"];
      return (
        <div className="growth-body">
          <p className="growth-head">
            <ScoreBadge score={r.score} label="Descripción actual" /> la
            descripción de ahora
          </p>
          {r.tips.length > 0 && (
            <ul className="growth-tips">
              {r.tips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          )}
          <pre className="growth-proposal">{r.improved}</pre>
          <div className="cluster">
            <button
              className="btn btn--sm"
              onClick={() => actions.applySeo(r.improved)}
            >
              Usar esta descripción
            </button>
            <CopyButton
              text={r.improved}
              label="Copiar"
              className="btn btn--sm"
            />
            {r.tags.length > 0 && (
              <CopyButton
                text={r.tags.join(", ")}
                label="Copiar etiquetas"
                className="btn btn--sm"
              />
            )}
          </div>
          {r.tags.length > 0 && (
            <p className="growth-tags">
              {r.tags.map((tag) => (
                <span key={tag} className="chip">
                  {tag}
                </span>
              ))}
            </p>
          )}
        </div>
      );
    }
    case "trends": {
      const r = result as GrowthResults["trends"];
      return (
        <div className="growth-body">
          {r.note && <p className="hint">{r.note}</p>}
          <ul className="growth-list">
            {r.ideas.map((idea) => (
              <li key={idea.title} className="growth-item">
                <p className="growth-main">{idea.title}</p>
                {idea.angle && (
                  <p className="hint">
                    <b>Ángulo:</b> {idea.angle}
                  </p>
                )}
                {idea.why && (
                  <p className="hint">
                    <b>Por qué:</b> {idea.why}
                  </p>
                )}
                {idea.hook && (
                  <p className="hint">
                    <b>Gancho:</b> {idea.hook}
                  </p>
                )}
                <div className="cluster">
                  <button
                    className="btn btn--sm"
                    onClick={() => actions.useTopic(idea.title)}
                  >
                    Usar como tema
                  </button>
                  <CopyButton
                    text={idea.title}
                    label="Copiar"
                    className="btn btn--sm"
                  />
                </div>
              </li>
            ))}
          </ul>
          {r.trends.length > 0 && (
            <>
              <p className="growth-sub">Lo que se está moviendo</p>
              <ul className="growth-tips">
                {r.trends.map((trend) => (
                  <li key={trend.topic}>
                    <b>{trend.topic}</b>
                    {trend.why ? `: ${trend.why}` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      );
    }
  }
}

/**
 * La revisión del guion entero: el puntaje (gancho, ritmo, claridad, título y
 * descripción) y dónde se va la gente, en una sola lista de qué cambiar y con
 * un solo botón que lo aplica todo. Cualquiera de las dos partes puede faltar
 * si su respuesta no llegó.
 */
export function ScriptReview({
  score,
  retention,
}: {
  score?: GrowthResults["score"];
  retention?: GrowthResults["retention"];
}) {
  const issues = retention?.issues ?? [];
  const actions = score?.actions ?? [];
  const fixes = [
    ...issues.map((i) => `${i.at ? `«${i.at}»: ` : ""}${i.problem} Qué hacer: ${i.fix}`),
    ...actions,
  ];
  return (
    <div className="growth-body">
      {score && (
        <>
          <p className="growth-head">
            <ScoreBadge score={score.total} label="Total" /> el video entero
          </p>
          <ul className="growth-parts">
            {score.parts.map((part) => (
              <li key={part.name}>
                <span className="growth-part-name">{part.name}</span>
                <span className={`growth-bar is-${scoreTone(part.score)}`} aria-hidden="true">
                  <span style={{ width: `${part.score}%` }} />
                </span>
                <b className="num">{part.score}</b>
                {part.note && <span className="hint growth-part-note">{part.note}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {retention && (
        <p className="growth-head">
          <ScoreBadge score={retention.score} label="Retención" /> {retention.summary}
        </p>
      )}
      {fixes.length > 0 && (
        <>
          <p className="growth-sub">Qué cambiar</p>
          <ul className="growth-list">
            {issues.map((issue) => (
              <li key={`${issue.at}-${issue.problem}`} className="growth-item">
                {issue.at && <q className="growth-quote">{issue.at}</q>}
                <p className="growth-main">{issue.problem}</p>
                <p className="hint">
                  <b>Qué hacer:</b> {issue.fix}
                </p>
              </li>
            ))}
            {actions.map((action) => (
              <li key={action} className="growth-item">
                <p className="growth-main">{action}</p>
              </li>
            ))}
          </ul>
          <p className="growth-sub">
            <ApplyRecommendation text={fixAllInstruction(fixes)} label="Aplicar todo" busy="Aplicando…" />
          </p>
        </>
      )}
      {retention && retention.keep.length > 0 && (
        <p className="hint">
          <b>Funciona, no lo toques:</b> {retention.keep.join(" · ")}
        </p>
      )}
    </div>
  );
}

type ApplyState =
  | { step: "idle" }
  | { step: "working" }
  | { step: "applied"; summary: string }
  | { step: "nothing"; summary: string };

/**
 * «Aplicar» una recomendación a todo el proceso. El modelo dice qué cambiaría
 * (guion, título, descripción); si solo cambia título o descripción se aplica
 * sin más. Si cambia el guion y ya hay escenas pintadas o una toma de voz, eso
 * queda desfasado: antes de rehacerlo —cuesta tiempo y créditos— se pregunta.
 */
function ApplyRecommendation({
  text,
  label = "Aplicar",
  busy = "Aplicando…",
}: {
  text: string;
  label?: string;
  busy?: string;
}) {
  const { planRecommendation, applyRecommendation } = useStudioActions();
  const confirm = useConfirm();
  const [state, setState] = useState<ApplyState>({ step: "idle" });

  const apply = async () => {
    setState({ step: "working" });
    const plan = await planRecommendation(text);
    if (!plan) return setState({ step: "idle" }); // el error sale en la tarjeta
    if (plan.changes.length === 0)
      return setState({ step: "nothing", summary: plan.summary });

    if (plan.regenerates.length > 0) {
      const accepted = await confirm({
        title: "¿Aplicar y regenerar?",
        message: `Esto cambia ${plan.changes.join(" y ")}. Lo que ya está hecho con el guion de antes quedaría desfasado, así que hay que rehacer:`,
        details: plan.regenerates.map((what) => REGENERATION_LABELS[what]),
        confirmLabel: "Aplicar y regenerar",
      });
      if (!accepted) return setState({ step: "idle" });
    }

    await applyRecommendation(plan);
    setState({ step: "applied", summary: plan.summary });
  };

  return (
    <span className="growth-apply">
      <button
        className="btn btn--sm"
        disabled={state.step === "working"}
        onClick={() => void apply()}
      >
        {state.step === "working"
          ? busy
          : state.step === "applied"
            ? `${label} otra vez`
            : label}
      </button>
      {state.step === "applied" && (
        <span className="hint">
          {" "}
          Aplicado{state.summary ? `: ${state.summary}` : "."}
        </span>
      )}
      {state.step === "nothing" && (
        <span className="hint">
          {" "}
          Sin cambios que hacer{state.summary ? `: ${state.summary}` : "."}
        </span>
      )}
    </span>
  );
}
