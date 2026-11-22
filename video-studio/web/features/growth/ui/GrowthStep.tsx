"use client";

import { STEP } from "@/domain/steps";
import { growthBlocker, scriptTimingNote } from "@/domain/growth";
import { useGrowth } from "@/features/growth/model/use-growth";
import { ScriptReview } from "@/features/growth/ui/GrowthResults";
import { useScript } from "@/features/script/model/use-script";
import { useStudio } from "@/features/studio/model/studio-context";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";
import { Step } from "@/shared/ui/Step";

/**
 * La revisión del guion entero, antes de pintar: el puntaje y dónde se va la
 * gente, pedidos a la vez y leídos juntos. Los demás consejos viven donde se
 * aplican: ganchos e ideas en Guion, título y SEO en Descripción.
 */
export function GrowthStep() {
  const growth = useGrowth();
  const script = useScript();
  const actions = useStudioActions();
  const { label } = useWriter();
  const { take, scenes, images } = useStudio();
  const timing = scriptTimingNote({
    aiScenes: scenes.items.filter((scene) => scene.prompt).length,
    canPaint: Boolean(images.choice),
    voiceTake: take.take !== null,
  });

  const pending = growth.pending.has("score") || growth.pending.has("retention");
  const blocker = !label ? "Añade una clave de API en «Modelo del guion»" : growthBlocker("score", script.topic, script.text);
  const score = growth.results.score;
  const retention = growth.results.retention;
  const review = () => {
    void actions.advise("score");
    void actions.advise("retention");
  };

  return (
    <Step
      n={STEP.growth}
      title="Optimizar"
      lead="Una revisión del guion entero: qué nota saca, dónde se va la gente y cómo subirla."
      note="puntaje y retención"
    >
      <p className={`hint${timing.late ? " warn" : ""}`}>{timing.text}</p>
      <section className="growth-card" id="growth-review" aria-labelledby="growth-review-t">
        <header className="growth-card-head">
          <h3 id="growth-review-t">Revisión del guion</h3>
          <button className="btn btn--sm" disabled={pending || blocker !== null} title={blocker ?? ""} onClick={review}>
            {pending ? "Pensando…" : score || retention ? "Revisar otra vez" : "Revisar"}
          </button>
        </header>
        <p className="hint">Es el criterio del modelo del guion, no datos en vivo de las plataformas.</p>
        {(score || retention) && <ScriptReview score={score} retention={retention} />}
        <ActionError place="growth" only="growth-score" />
        <ActionError place="growth" only="growth-retention" />
      </section>
    </Step>
  );
}
