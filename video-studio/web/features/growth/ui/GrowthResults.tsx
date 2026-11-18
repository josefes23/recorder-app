"use client";

import { scoreTone, type GrowthKind, type GrowthResults } from "@/domain/growth";
import { CopyButton } from "@/shared/ui/CopyButton";

export function ScoreBadge({ score, label }: { score: number; label?: string }) {
  return (
    <span className={`growth-score is-${scoreTone(score)}`} title={label ? `${label}: ${score} de 100` : `${score} de 100`}>
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
                {hook.type && <span className="chip">{hook.type}</span>} {hook.text}
              </p>
              {hook.why && <p className="hint">{hook.why}</p>}
              <div className="cluster">
                <button
                  className="btn btn--sm"
                  onClick={() => actions.applyHook(hook.text)}
                  disabled={appliedHook === hook.text}
                  title="Lo pone al principio del guion; si ya pusiste otro gancho, lo sustituye"
                >
                  {appliedHook === hook.text ? "En el guion" : "Usar como primera frase"}
                </button>
                <CopyButton text={hook.text} label="Copiar" className="btn btn--sm" />
              </div>
            </li>
          ))}
        </ol>
      );
    }
    case "retention": {
      const r = result as GrowthResults["retention"];
      return (
        <div className="growth-body">
          <p className="growth-head">
            <ScoreBadge score={r.score} label="Retención" /> {r.summary}
          </p>
          <ul className="growth-list">
            {r.issues.map((issue) => (
              <li key={`${issue.at}-${issue.problem}`} className="growth-item">
                {issue.at && <q className="growth-quote">{issue.at}</q>}
                <p className="growth-main">{issue.problem}</p>
                <p className="hint">
                  <b>Qué hacer:</b> {issue.fix}
                </p>
              </li>
            ))}
          </ul>
          {r.keep.length > 0 && (
            <p className="hint">
              <b>Funciona, no lo toques:</b> {r.keep.join(" · ")}
            </p>
          )}
        </div>
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
                <CopyButton text={title.text} label="Copiar" className="btn btn--sm" />
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
            <ScoreBadge score={r.score} label="Descripción actual" /> la descripción de ahora
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
            <button className="btn btn--sm" onClick={() => actions.applySeo(r.improved)}>
              Usar esta descripción
            </button>
            <CopyButton text={r.improved} label="Copiar" className="btn btn--sm" />
            {r.tags.length > 0 && <CopyButton text={r.tags.join(", ")} label="Copiar etiquetas" className="btn btn--sm" />}
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
    case "score": {
      const r = result as GrowthResults["score"];
      return (
        <div className="growth-body">
          <p className="growth-head">
            <ScoreBadge score={r.total} label="Total" /> el video entero
          </p>
          <ul className="growth-parts">
            {r.parts.map((part) => (
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
          {r.actions.length > 0 && (
            <>
              <p className="growth-sub">Lo que más lo subiría</p>
              <ol className="growth-tips">
                {r.actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ol>
            </>
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
                  <button className="btn btn--sm" onClick={() => actions.useTopic(idea.title)}>
                    Usar como tema
                  </button>
                  <CopyButton text={idea.title} label="Copiar" className="btn btn--sm" />
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
