"use client";

import { useState } from "react";

import { canSaveImages, imageProviderOf } from "@/domain/illustration";
import { useImages } from "@/features/illustrations/model/use-images";
import { useStatus } from "@/features/studio/model/use-studio-actions";
import { Disclosure } from "@/shared/ui/Disclosure";
import { Field } from "@/shared/ui/Field";

const IMAGE_SETTINGS_ID = "image-settings";

/** Despliega el panel y lleva la vista hasta él. */
export function revealImageSettings() {
  const panel = document.getElementById(IMAGE_SETTINGS_ID);
  if (!(panel instanceof HTMLDetailsElement)) return;
  panel.open = true;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** Cómo conseguir los datos de cada generador, en una línea. */
const HELP: Record<string, string> = {
  cloudflare:
    "Cuenta gratuita en dash.cloudflare.com. En Workers AI, la opción de usar la API REST enseña el ID de cuenta y crea un token con permiso de Workers AI.",
  google:
    "La misma clave que el guion con Gemini. Las imágenes no tienen nivel gratuito: activa la facturación en ai.dev/rate-limit.",
};

export function ImageSettingsPanel() {
  const images = useImages();
  const { busy } = useStatus();

  /* El generador que se edita vive en el slice, para que otro sitio pueda
     traer aquí al usuario con uno ya elegido. El resto es estado del formulario. */
  const [pickedModel, setPickedModel] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  const settings = images.settings;
  if (!settings) return null;

  const current = imageProviderOf(settings, images.editing ?? settings.provider);
  // Un modelo elegido para otro generador no vale para este.
  const model = pickedModel && current.models.some((m) => m.id === pickedModel) ? pickedModel : current.model;

  const pickProvider = (id: string) => {
    images.edit(id);
    setPickedModel(null); // cada generador recupera el modelo que tuviera guardado
    setValues({});
    setSaved(false);
  };

  const save = async () => {
    const ok = await images.save({ provider: current.id, model, values });
    if (!ok) return;
    setValues({}); // ya está en el .env: fuera del navegador
    setPickedModel(null);
    setSaved(true);
  };

  return (
    <Disclosure
      id={IMAGE_SETTINGS_ID}
      summary="Generador de imágenes"
      note={settings.label ?? "sin configurar"}
    >
      <Field id="images-provider" label="Generador">
        <select id="images-provider" value={current.id} onChange={(e) => pickProvider(e.target.value)}>
          {settings.providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} — {p.note}
            </option>
          ))}
        </select>
      </Field>

      {current.fields.map((field) => (
        <Field
          key={field.env}
          id={`images-${field.env}`}
          label={field.label}
          value={field.hint ? `guardado ${field.hint}` : "falta"}
        >
          <input
            id={`images-${field.env}`}
            type={field.secret ? "password" : "text"}
            value={values[field.env] ?? ""}
            onChange={(e) => {
              setValues((prev) => ({ ...prev, [field.env]: e.target.value }));
              setSaved(false);
            }}
            placeholder={field.hint ? "cámbialo o déjalo vacío" : field.label}
            autoComplete="off"
            spellCheck={false}
          />
        </Field>
      ))}

      <Field id="images-model" label="Modelo">
        <select
          id="images-model"
          value={model}
          onChange={(e) => {
            setPickedModel(e.target.value);
            setSaved(false);
          }}
        >
          {current.models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label} — {m.note}
            </option>
          ))}
        </select>
      </Field>

      {HELP[current.id] && <p className="hint">{HELP[current.id]}</p>}

      <div className="cluster">
        <button
          className="btn"
          disabled={!canSaveImages(current, values) || busy !== null}
          onClick={save}
        >
          {busy === "images" ? "Guardando…" : "Guardar"}
        </button>
        <span className="hint">
          {saved ? "Guardado. Ya puedes generar escenas." : "Se guarda en video-studio/.env"}
        </span>
      </div>
    </Disclosure>
  );
}
