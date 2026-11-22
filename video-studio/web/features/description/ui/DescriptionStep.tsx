"use client";

import { STEP } from "@/domain/steps";
import {
  DESCRIPTION_LIMIT,
  descriptionLength,
  platformWarning,
  visiblePart,
} from "@/domain/description";
import { GrowthCard } from "@/features/growth/ui/GrowthCard";
import { useDescription } from "@/features/description/model/use-description";
import { useScript } from "@/features/script/model/use-script";
import { useStudioActions } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { useWriter } from "@/features/writer/model/use-writer";
import { CopyButton } from "@/shared/ui/CopyButton";
import { Step } from "@/shared/ui/Step";

/**
 * El texto con que se publica: palabras clave al principio, un resumen del
 * video y unos hashtags. Lo escribe el modelo del guion o el usuario, y viaja
 * con el render para copiarlo al publicar.
 */
export function DescriptionStep() {
  const description = useDescription();
  const script = useScript();
  const actions = useStudioActions();
  const { label } = useWriter();

  const length = descriptionLength(description.text);
  const warning = platformWarning(description.text);
  const visible = visiblePart(description.text);

  return (
    <Step
      n={STEP.description}
      title="Descripción"
      lead="El texto con el que se publica el video: que te encuentren al buscar."
      note={
        length > 0 ? (
          <>
            <b className="num">{length}</b> / {DESCRIPTION_LIMIT}
          </>
        ) : (
          "para que te encuentren al buscar"
        )
      }
    >
      <div className="field">
        <label htmlFor="description">Texto para publicar</label>
        <textarea
          id="description"
          rows={6}
          maxLength={DESCRIPTION_LIMIT}
          value={description.text}
          onChange={(e) => description.setText(e.target.value)}
          placeholder={
            "Qué dijo Jesús sobre Dios según los evangelios: tres enseñanzas que…\n\n#jesus #biblia"
          }
        />
        <p className="hint">
          Las palabras clave van al principio: es lo que más pesa en los buscadores y lo único
          que se ve antes de «más». Luego, un resumen del video y unos hashtags.
        </p>
        {visible && (
          <p className="hint">
            Antes de «más» se lee: <q className="description-visible">{visible}</q>
          </p>
        )}
        {warning && <p className="hint warn">{warning}</p>}
      </div>

      <div className="cluster">
        <button
          className="btn"
          disabled={!label || description.writing || !script.text.trim()}
          onClick={actions.writeDescription}
          title={
            !label
              ? "Añade una clave de API en «Modelo del guion»"
              : !script.text.trim()
                ? "Escribe primero el guion: la descripción lo resume"
                : ""
          }
        >
          {description.writing
            ? "Escribiendo…"
            : description.text.trim()
              ? "Reescribir con IA"
              : "Escribir con IA"}
        </button>
        <CopyButton text={description.text} label="Copiar" className="btn" />
        {description.writing && (
          <span className="hint">La escribe el modelo del guion con el guion y el título de la portada.</span>
        )}
      </div>
      <ActionError place="description" />

      <div className="growth-grid">
        <GrowthCard kind="titles" />
        <GrowthCard kind="seo" needs={description.text.trim() ? null : "Escribe o genera primero la descripción."} />
      </div>
    </Step>
  );
}
