"use client";

import { STEP } from "@/domain/steps";
import { useEffect, useRef, useState } from "react";

import type { ElevenLabs } from "@/domain/config";
import { speakersIn } from "@/domain/dialogue";
import { signed, type Voice } from "@/domain/voice";
import { useProduction } from "@/features/production/model/use-production";
import { useScript } from "@/features/script/model/use-script";
import { useStudio } from "@/features/studio/model/studio-context";
import { useStatus, useStudioActions } from "@/features/studio/model/use-studio-actions";
import { useVoice, useVoiceCatalog } from "@/features/voice/model/use-voice";
import { Field } from "@/shared/ui/Field";
import { Select, type SelectOption } from "@/shared/ui/Select";
import { Slider } from "@/shared/ui/Slider";
import { Step } from "@/shared/ui/Step";

export function VoiceStep() {
  const voice = useVoice();
  const catalog = useVoiceCatalog();
  const production = useProduction();
  const { text } = useScript();
  const speakers = production.dialogue ? speakersIn(text) : [];
  const { config } = useStudio();
  const options = voiceOptions(catalog);
  const elevenIds = new Set(catalog.filter((v) => v.provider === "elevenlabs").map((v) => v.id));
  const usesEleven =
    elevenIds.has(voice.id) || speakers.some((name) => elevenIds.has(production.voices[name] ?? ""));

  /* Sin nota al lado del título: el desplegable ya dice qué voz está puesta. */
  return (
    <Step n={STEP.voice} title="Voz" lead="Elige quién lo dice y cómo suena. Puedes escuchar cada voz antes de decidir.">
      <Field id="voice" label={production.dialogue ? "Narrador" : "Locutor"}>
        <div className="cluster">
          <Select id="voice" value={voice.id} options={options} onChange={voice.setId} />
          <VoiceSample voice={catalog.find((v) => v.id === voice.id)} />
        </div>
      </Field>

      {production.dialogue &&
        (speakers.length ? (
          <div className="fields">
            {speakers.map((speaker) => (
              <Field key={speaker} id={`voice-${speaker}`} label={speaker}>
                <div className="cluster">
                  <Select
                    id={`voice-${speaker}`}
                    value={production.voices[speaker] ?? ""}
                    options={options}
                    onChange={(id) => production.setVoice(speaker, id)}
                  />
                  <VoiceSample voice={catalog.find((v) => v.id === production.voices[speaker])} />
                </div>
              </Field>
            ))}
          </div>
        ) : (
          <p className="hint">
            Cada personaje aparece aquí en cuanto el guion tenga una línea que empiece con su nombre
            en mayúsculas («ANA: …»). Con el diálogo activado, el modelo del guion ya lo escribe así.
          </p>
        ))}

      {config?.elevenlabs && <ElevenLabsAccount account={config.elevenlabs} />}

      <div className="fields">
        <Slider
          id="rate" label="Velocidad" value={voice.rate} display={`${signed(voice.rate)} %`}
          min={-25} max={35} onChange={voice.setRate}
        />
        <Slider
          id="pitch" label="Tono" value={voice.pitch} display={`${signed(voice.pitch)} Hz`}
          min={-30} max={30} step={2} onChange={voice.setPitch}
        />
      </div>
      {usesEleven && (
        <p className="hint">
          Con ElevenLabs la velocidad sí cuenta (entre 0,7× y 1,2×), pero el tono no. Cada voz generada
          gasta créditos de tu cuenta; las de edge-tts son gratis.
        </p>
      )}
    </Step>
  );
}

/** edge-tts y ElevenLabs conviven en la misma lista: se agrupan para que se vea cuál gasta créditos. */
function voiceOptions(voices: Voice[]): SelectOption[] {
  const edge = voices.filter((v) => v.provider !== "elevenlabs");
  const eleven = voices.filter((v) => v.provider === "elevenlabs");
  const as = (list: Voice[], group?: string): SelectOption[] =>
    list.map((v) => ({ value: v.id, label: v.label, group }));
  return eleven.length
    ? [...as(edge, "edge-tts · gratis"), ...as(eleven, "ElevenLabs · gasta créditos")]
    : as(edge);
}

/** La clave de ElevenLabs: con ella sus voces se suman a la lista; sin ella todo sigue con edge-tts. */
function ElevenLabsAccount({ account }: { account: ElevenLabs }) {
  const { saveElevenLabsKey, refreshElevenLabsVoices } = useStudioActions();
  const { busy } = useStatus();
  const [key, setKey] = useState("");
  const saving = busy === "elevenlabs";

  const save = async (value: string) => {
    if (await saveElevenLabsKey(value)) setKey("");
  };

  if (account.ready) {
    return (
      <div className="cluster">
        <span className="hint">
          {account.problem
            ? `ElevenLabs: ${account.problem}`
            : `ElevenLabs conectado · ${account.voices} voces de tu cuenta (modelo ${account.model}).`}
        </span>
        <button className="btn" disabled={saving} onClick={() => refreshElevenLabsVoices()}>
          {saving ? "…" : "Actualizar voces"}
        </button>
        <button className="btn" disabled={saving} onClick={() => save("")}>
          Quitar clave
        </button>
      </div>
    );
  }
  return (
    <Field id="elevenlabs-key" label="Clave de ElevenLabs (opcional)">
      <div className="cluster">
        <input
          id="elevenlabs-key"
          type="password"
          autoComplete="off"
          placeholder="Pega tu API key para sumar sus voces"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <button className="btn" disabled={saving || !key.trim()} onClick={() => save(key)}>
          {saving ? "…" : "Guardar"}
        </button>
      </div>
    </Field>
  );
}

/**
 * Escuchar una voz antes de elegirla. «Probar» la hace decir una frase en
 * español con la velocidad de ahora —gratis con edge-tts; con ElevenLabs gasta
 * unos pocos créditos, una sola vez, porque la misma prueba se reutiliza—.
 * «Muestra» es la que publica ElevenLabs de la voz, sin gastar nada.
 */
function VoiceSample({ voice }: { voice: Voice | undefined }) {
  const { sampleVoice } = useStudioActions();
  const { busy } = useStatus();
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState<"try" | "sample" | null>(null);
  const id = voice?.id;

  const stop = () => {
    audio.current?.pause();
    audio.current = null;
    setPlaying(null);
  };

  /* Al cambiar de voz o salir del paso, lo que sonaba se corta. */
  useEffect(() => stop, [id]);

  if (!voice) return null;

  const play = (kind: "try" | "sample", url: string) => {
    const next = new Audio(url);
    next.onended = () => setPlaying(null);
    next.onerror = () => setPlaying(null);
    audio.current = next;
    setPlaying(kind);
    next.play().catch(() => setPlaying(null));
  };

  const toggle = async (kind: "try" | "sample") => {
    if (playing === kind) return stop();
    stop();
    if (kind === "sample" && voice.preview) return play(kind, voice.preview);
    const url = await sampleVoice(voice.id);
    if (url) play(kind, url);
  };

  const paid = voice.provider === "elevenlabs";
  const generating = busy === "sample";
  return (
    <>
      <button
        type="button"
        className="btn"
        disabled={generating}
        title={paid ? "Gasta unos pocos créditos de ElevenLabs la primera vez" : "Gratis"}
        onClick={() => toggle("try")}
      >
        {generating ? "…" : playing === "try" ? "■ Parar" : "▶ Probar"}
      </button>
      {voice.preview && (
        <button type="button" className="btn" title="Muestra de ElevenLabs, sin gastar créditos" onClick={() => toggle("sample")}>
          {playing === "sample" ? "■ Parar" : "▶ Muestra"}
        </button>
      )}
    </>
  );
}
