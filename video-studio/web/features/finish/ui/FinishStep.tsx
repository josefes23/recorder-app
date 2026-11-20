"use client";

import {
  cardsSeconds,
  colorActive,
  DEFAULT_FINISH,
  finishSummary,
  isRecommended,
  INTRO_LIMIT,
  LOOKS,
  OUTRO_LIMIT,
  type Finish,
  type LookId,
  withRecommended,
} from "@/domain/finish";
import { signed } from "@/domain/voice";
import { STEP } from "@/domain/steps";
import { useProduction } from "@/features/production/model/use-production";
import { useScript } from "@/features/script/model/use-script";
import { Field } from "@/shared/ui/Field";
import { Slider } from "@/shared/ui/Slider";
import { Step } from "@/shared/ui/Step";

/** -1…1 en el servidor; en pantalla, -100…100. */
const percent = (value: number) => Math.round(value * 100);

/**
 * El acabado: lo que se le hace al video una vez armado, para que suene y se
 * vea mejor. Todo es opcional y está apagado: sin tocar nada, el video sale
 * como siempre. Se hace en el mismo render, sin una segunda codificación.
 */
export function FinishStep() {
  const production = useProduction();
  const script = useScript();
  const { finish } = production;
  const summary = finishSummary(finish);
  const extra = cardsSeconds(finish.cards);

  const set = (changes: Partial<Finish>) => production.setFinish({ ...finish, ...changes });
  const setColor = (changes: Partial<Finish["color"]>) => set({ color: { ...finish.color, ...changes } });
  const toggle = (group: "audio", key: "clean" | "normalize", on: boolean) =>
    set({ [group]: { ...finish[group], [key]: on } });

  /* La primera frase con fuerza hace de título de la tarjeta de entrada. */
  const suggestedIntro = script.topic.trim();

  return (
    <Step
      n={STEP.finish}
      title="Acabado"
      lead="Retoques finales para que suene y se vea mejor: audio, color, ritmo y tarjetas. Todo es opcional."
      note={summary.length ? summary.join(" · ") : "sin retoques"}
    >
      <div className="cluster">
        <button
          type="button"
          className="btn btn--sm"
          disabled={isRecommended(finish)}
          onClick={() => production.setFinish(withRecommended(finish))}
          title="Voz con presencia, volumen parejo y pausas recortadas. No toca el color ni las tarjetas."
        >
          {isRecommended(finish) ? "Recomendado puesto" : "Aplicar lo recomendado"}
        </button>
        <span className="hint">Audio y ritmo con un clic; el color y las tarjetas, a tu gusto.</span>
      </div>

      <section className="finish-group" aria-labelledby="finish-audio">
        <h3 id="finish-audio" className="finish-title">Audio</h3>
        <label className="cluster check" htmlFor="finish-clean">
          <input
            id="finish-clean"
            type="checkbox"
            checked={finish.audio.clean}
            onChange={(e) => toggle("audio", "clean", e.target.checked)}
          />
          <span className="hint">
            <b>Voz con presencia:</b> quita graves que ensucian, iguala el volumen de la voz y le da más brillo.
          </span>
        </label>
        <label className="cluster check" htmlFor="finish-normalize">
          <input
            id="finish-normalize"
            type="checkbox"
            checked={finish.audio.normalize}
            onChange={(e) => toggle("audio", "normalize", e.target.checked)}
          />
          <span className="hint">
            <b>Volumen parejo:</b> lleva la mezcla final (voz y música) a −14 LUFS, el nivel de YouTube, Instagram
            y TikTok. Así no suena más bajo que el resto.
          </span>
        </label>
      </section>

      <section className="finish-group" aria-labelledby="finish-color">
        <div className="spread">
          <h3 id="finish-color" className="finish-title">Color</h3>
          {colorActive(finish.color) && (
            <button className="btn btn--sm" onClick={() => setColor(DEFAULT_FINISH.color)}>
              Quitar el color
            </button>
          )}
        </div>
        <div className="tabs finish-looks" role="radiogroup" aria-label="Look">
          {LOOKS.map((look) => (
            <button
              key={look.id}
              type="button"
              role="radio"
              aria-checked={finish.color.look === look.id}
              className={`tab${finish.color.look === look.id ? " is-on" : ""}`}
              title={look.hint}
              onClick={() => setColor({ look: look.id as LookId })}
            >
              {look.label}
            </button>
          ))}
        </div>
        <div className="fields">
          <Slider
            id="finish-exposure" label="Exposición" value={percent(finish.color.exposure)}
            display={signed(percent(finish.color.exposure))} min={-100} max={100} step={5}
            onChange={(v) => setColor({ exposure: v / 100 })}
          />
          <Slider
            id="finish-contrast" label="Contraste" value={percent(finish.color.contrast)}
            display={signed(percent(finish.color.contrast))} min={-100} max={100} step={5}
            onChange={(v) => setColor({ contrast: v / 100 })}
          />
          <Slider
            id="finish-saturation" label="Saturación" value={percent(finish.color.saturation)}
            display={signed(percent(finish.color.saturation))} min={-100} max={100} step={5}
            onChange={(v) => setColor({ saturation: v / 100 })}
          />
        </div>
        <p className="hint">
          Solo se aplica al fondo: los subtítulos no se tiñen. El botón «Fotograma» de la derecha enseña cómo queda.
        </p>
      </section>

      <section className="finish-group" aria-labelledby="finish-pace">
        <h3 id="finish-pace" className="finish-title">Ritmo</h3>
        <label className="cluster check" htmlFor="finish-tighten">
          <input
            id="finish-tighten"
            type="checkbox"
            checked={finish.pace.tighten}
            onChange={(e) => set({ pace: { tighten: e.target.checked } })}
          />
          <span className="hint">
            <b>Recortar pausas largas:</b> acorta los silencios de la voz. Los subtítulos y las escenas se
            re-sincronizan solos, así que el video dura un poco menos.
          </span>
        </label>
      </section>

      <section className="finish-group" aria-labelledby="finish-cards">
        <h3 id="finish-cards" className="finish-title">Tarjetas de entrada y cierre</h3>
        <Field id="finish-intro" label="Entrada" value={finish.cards.intro.length ? `${finish.cards.intro.length}/${INTRO_LIMIT}` : "sin tarjeta"}>
          <div className="cluster">
            <input
              id="finish-intro"
              type="text"
              maxLength={INTRO_LIMIT}
              placeholder="Lo que *nadie* te dice sobre el sueño"
              value={finish.cards.intro}
              onChange={(e) => set({ cards: { ...finish.cards, intro: e.target.value } })}
            />
            {suggestedIntro && finish.cards.intro !== suggestedIntro && (
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => set({ cards: { ...finish.cards, intro: suggestedIntro.slice(0, INTRO_LIMIT) } })}
              >
                Usar el tema
              </button>
            )}
          </div>
        </Field>
        <Field id="finish-outro" label="Cierre" value={finish.cards.outro.length ? `${finish.cards.outro.length}/${OUTRO_LIMIT}` : "sin tarjeta"}>
          <input
            id="finish-outro"
            type="text"
            maxLength={OUTRO_LIMIT}
            placeholder="Sígueme para *más* consejos"
            value={finish.cards.outro}
            onChange={(e) => set({ cards: { ...finish.cards, outro: e.target.value } })}
          />
        </Field>
        <p className="hint">
          Lo que va entre *asteriscos* sale resaltado.
          {extra > 0 && ` Las tarjetas suman ${extra.toFixed(1).replace(".", ",")} s al video.`}
        </p>
      </section>
    </Step>
  );
}
