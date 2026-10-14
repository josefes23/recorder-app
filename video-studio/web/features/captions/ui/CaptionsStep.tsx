"use client";

import { useCaptions } from "@/features/captions/model/use-captions";
import { Disclosure } from "@/shared/ui/Disclosure";
import { Slider } from "@/shared/ui/Slider";
import { Step } from "@/shared/ui/Step";

export function CaptionsStep() {
  const { style, setField } = useCaptions();

  return (
    <Step n={3} title="Subtítulos">
      {/* Arriba lo que se retoca en cada video; lo demás se ajusta una vez */}
      <div className="fields">
        <Slider
          id="font_size" label="Tamaño" value={style.font_size} display={`${style.font_size} px`}
          min={56} max={128} step={2} onChange={(v) => setField("font_size", v)}
        />
        <Slider
          id="y_ratio" label="Altura en el cuadro" value={style.y_ratio}
          display={style.y_ratio.toFixed(2)}
          min={0.15} max={0.75} step={0.01} onChange={(v) => setField("y_ratio", v)}
        />
      </div>

      <Disclosure summary="Ajuste fino" note="borde, corte de línea y animación">
        <div className="fields">
          <Slider
            id="stroke" label="Borde" value={style.stroke} display={`${style.stroke} px`}
            min={0} max={16} onChange={(v) => setField("stroke", v)}
          />
          <Slider
            id="max_chars" label="Caracteres por bloque" value={style.max_chars}
            min={16} max={46} onChange={(v) => setField("max_chars", v)}
          />
          <Slider
            id="max_lines" label="Líneas máximas" value={style.max_lines}
            min={1} max={4} onChange={(v) => setField("max_lines", v)}
          />
          <div className="field">
            <span className="field-label">Entrada</span>
            <label className="cluster" htmlFor="animate">
              <input
                id="animate"
                type="checkbox"
                checked={style.animate}
                onChange={(e) => setField("animate", e.target.checked)}
              />
              <span className="hint">Animar cada bloque al aparecer</span>
            </label>
          </div>
        </div>
      </Disclosure>
    </Step>
  );
}
