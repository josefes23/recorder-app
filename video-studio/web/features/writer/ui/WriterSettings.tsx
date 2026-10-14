"use client";

import { useState } from "react";

import { canSave, modelGroups, providerOf } from "@/domain/writer";
import { useStatus } from "@/features/studio/model/use-studio-actions";
import { useWriter } from "@/features/writer/model/use-writer";
import { Disclosure } from "@/shared/ui/Disclosure";
import { Field } from "@/shared/ui/Field";

const PLACEHOLDER: Record<string, string> = {
  nvidia: "nvapi-…",
  google: "AIza…",
  deepseek: "sk-…",
  anthropic: "sk-ant-…",
};

export function WriterSettings() {
  const writer = useWriter();
  const { busy } = useStatus();

  /* null = «lo que diga el servidor». Así el formulario refleja lo guardado sin
     copiarlo a estado, y tras guardar vuelve a derivarse de la respuesta. */
  const [picked, setPicked] = useState<string | null>(null);
  const [pickedModel, setPickedModel] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);

  const settings = writer.settings;
  if (!settings) return null;

  const provider = picked ?? settings.provider;
  const current = providerOf(settings, provider);
  const model = pickedModel ?? current.model;

  const pickProvider = (id: string) => {
    setPicked(id);
    setPickedModel(null); // cada proveedor recupera el modelo que tuviera guardado
    setApiKey("");
    setSaved(false);
  };

  const save = async () => {
    const ok = await writer.save({ provider, api_key: apiKey, model });
    if (!ok) return;
    setApiKey(""); // ya está en el .env: fuera del navegador
    setPicked(null);
    setPickedModel(null);
    setSaved(true);
  };

  return (
    <Disclosure summary="Modelo del guion" note={settings.label ?? "sin clave"}>
      <Field id="writer-provider" label="Proveedor">
        <select id="writer-provider" value={provider} onChange={(e) => pickProvider(e.target.value)}>
          {settings.providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} — {p.note}
            </option>
          ))}
        </select>
      </Field>

      <Field
        id="writer-key"
        label="Clave de API"
        value={current.key_hint ? `guardada ${current.key_hint}` : "ninguna"}
      >
        <input
          id="writer-key"
          type="password"
          value={apiKey}
          onChange={(e) => {
            setApiKey(e.target.value);
            setSaved(false);
          }}
          placeholder={current.key_hint ? "cámbiala o déjalo vacío" : PLACEHOLDER[current.id]}
          autoComplete="off"
        />
      </Field>

      <Field id="writer-model" label="Modelo">
        <select
          id="writer-model"
          value={model}
          onChange={(e) => {
            setPickedModel(e.target.value);
            setSaved(false);
          }}
        >
          {modelGroups(current).map((group) => (
            <optgroup key={group} label={group}>
              {current.models
                .filter((m) => m.group === group)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </Field>

      <div className="cluster">
        <button
          className="btn"
          disabled={!canSave(current, apiKey) || busy !== null}
          onClick={save}
        >
          {busy === "writer" ? "Guardando…" : "Guardar"}
        </button>
        <span className="hint">
          {saved
            ? "Guardado. Ya puedes escribir el guion."
            : `Se guarda en video-studio/.env como ${current.key_env}`}
        </span>
      </div>
    </Disclosure>
  );
}
