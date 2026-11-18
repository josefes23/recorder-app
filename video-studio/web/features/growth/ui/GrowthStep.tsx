"use client";

import { GROWTH_KINDS, GROWTH_LABELS, growthBlocker, type GrowthKind } from "@/domain/growth";
import { useGrowth } from "@/features/growth/model/use-growth";
import { GrowthResult } from "@/features/growth/ui/GrowthResults";
import { useScript } from "@/features/script/model/use-script";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";
import { Step } from "@/shared/ui/Step";

const WHAT: Record<GrowthKind, string> = {
  hooks: "Cinco primeras frases para los tres segundos que deciden si se quedan.",
  retention: "Dónde se va la gente en tu guion y qué cambiar.",
  titles: "Seis títulos con nota, comparados con el que ya tienes.",
  seo: "Evalúa la descripción y propone una mejor, con etiquetas.",
  score: "Una nota por gancho, ritmo, claridad, título y descripción.",
  trends: "Ideas de videos nuevas en tu nicho y qué formatos funcionan.",
};

/**
 * El asistente de crecimiento: lo que haría un vidIQ, con el modelo del guion y
 * sobre el video que hay abierto. Son criterios del modelo, no datos en vivo.
 */
export function GrowthStep() {
  const growth = useGrowth();
  const script = useScript();
  const actions = useStudioActions();
  const { label } = useWriter();

  return (
    <Step n={7} title="Optimizar" note="ganchos, retención, títulos, SEO y puntaje">
      <p className="hint">
        Consejos del modelo del guion sobre este video. No consulta datos en vivo de YouTube, TikTok ni
        Instagram: son criterio de un editor que conoce cómo funcionan, no estadísticas.
      </p>
      <div className="growth-grid">
        {GROWTH_KINDS.map((kind) => {
          const pending = growth.pending.has(kind);
          const blocker = !label ? "Añade una clave de API en «Modelo del guion»" : growthBlocker(kind, script.topic, script.text);
          const result = growth.results[kind];
          return (
            <section key={kind} className="growth-card" id={`growth-${kind}`} aria-labelledby={`growth-${kind}-t`}>
              <header className="growth-card-head">
                <h3 id={`growth-${kind}-t`}>{GROWTH_LABELS[kind]}</h3>
                <button
                  className="btn btn--sm"
                  disabled={pending || blocker !== null}
                  title={blocker ?? ""}
                  onClick={() => void actions.advise(kind)}
                >
                  {pending ? "Pensando…" : result ? "Pedir otra vez" : "Pedir"}
                </button>
              </header>
              <p className="hint">{WHAT[kind]}</p>
              {result && (
                <GrowthResult
                  kind={kind}
                  result={result}
                  appliedHook={growth.appliedHook}
                  actions={{ ...actions, useTopic: script.setTopic }}
                />
              )}
              <ActionError place="growth" only={`growth-${kind}`} />
            </section>
          );
        })}
      </div>
    </Step>
  );
}
