"use client";

import { useState } from "react";

import { CORRECTION_LIMIT } from "@/domain/illustration";
import { useImages } from "@/features/illustrations/model/use-images";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { useWriter } from "@/features/writer/model/use-writer";
import { Field } from "@/shared/ui/Field";

import { ImageChoiceSelect } from "./ImageChoiceSelect";
import { UnconfiguredProviders } from "./UnconfiguredProviders";

type Props = {
  /** Escena cuya imagen se corrige. */
  index: number;
  /** De qué partir: los fallos que vio el revisor, o vacío. */
  initial: string;
  onDone: () => void;
};

/**
 * Contarle a la IA qué está mal en la imagen de una escena. No pinta otra: el
 * generador parte de esta y cambia solo lo que se le dice.
 */
export function SceneImageCorrector({ index, initial, onDone }: Props) {
  const images = useImages();
  const writer = useWriter();
  const actions = useStudioActions();
  const { busy } = useStatus();
  const [correction, setCorrection] = useState(initial);

  const id = `scene-fix-${index}`;
  const ready = images.choice !== null;
  const checked = images.review && writer.seesImages;

  const correct = async () => {
    if (await actions.correctScene(index, correction)) onDone();
  };

  return (
    <div className="scene-editor">
      <Field id={id} label="Qué está mal en la imagen">
        <textarea
          id={id}
          rows={3}
          maxLength={CORRECTION_LIMIT}
          value={correction}
          onChange={(e) => setCorrection(e.target.value)}
          placeholder="La mujer de la izquierda tiene seis dedos en la mano derecha; hay letras inventadas en el cielo"
        />
      </Field>
      <p className="hint">
        Di qué falla y dónde. La IA parte de esta misma imagen y cambia solo eso; lo demás se
        queda igual
        {checked ? `, y ${writer.label} comprueba que quedó arreglado` : ""}. La original sigue en
        la galería.
      </p>

      {ready ? (
        <Field id={`${id}-choice`} label="Corregir con">
          <ImageChoiceSelect id={`${id}-choice`} />
        </Field>
      ) : (
        <UnconfiguredProviders />
      )}

      <div className="cluster">
        <button
          className="btn btn--primary"
          disabled={!ready || !correction.trim() || busy !== null}
          onClick={correct}
        >
          {busy === `correct-${index}` ? "Pidiendo…" : "Corregir imagen"}
        </button>
        <button className="btn" onClick={onDone}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
