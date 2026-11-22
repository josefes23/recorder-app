"use client";

import { GROWTH_LABELS, growthBlocker, type GrowthKind } from "@/domain/growth";
import { useGrowth } from "@/features/growth/model/use-growth";
import { GrowthResult } from "@/features/growth/ui/GrowthResults";
import { useScript } from "@/features/script/model/use-script";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";

/** Los consejos que viven en el paso donde se aplican; la revisión del guion tiene su propio paso. */
export type PlacedKind = Exclude<GrowthKind, "score" | "retention">;

const WHAT: Record<PlacedKind, string> = {
  hooks: "Cinco primeras frases para los tres segundos que deciden si se quedan.",
  trends: "Ideas de videos para tu nicho y qué formatos funcionan. Es criterio del modelo, no datos en vivo.",
  titles: "Seis títulos para publicar, con nota, comparados con el de la portada.",
  seo: "Puntúa la descripción y propone una mejor, con etiquetas.",
};

/**
 * Un consejo del modelo del guion, pedido y leído en el mismo sitio: los
 * ganchos y las ideas en Guion, el título y el SEO en Descripción. El id
 * `growth-<kind>` es también donde sale su error (`ActionError`).
 */
export function GrowthCard({ kind, needs }: { kind: PlacedKind; needs?: string | null }) {
  const growth = useGrowth();
  const script = useScript();
  const actions = useStudioActions();
  const { label } = useWriter();

  const pending = growth.pending.has(kind);
  const blocker = !label
    ? "Añade una clave de API en «Modelo del guion»"
    : (growthBlocker(kind, script.topic, script.text) ?? needs ?? null);
  const result = growth.results[kind];

  return (
    <section className="growth-card" id={`growth-${kind}`} aria-labelledby={`growth-${kind}-t`}>
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
}
