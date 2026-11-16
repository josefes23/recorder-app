"use client";

import { speakersIn } from "@/domain/dialogue";
import { signed } from "@/domain/voice";
import { useProduction } from "@/features/production/model/use-production";
import { useScript } from "@/features/script/model/use-script";
import { useVoice, useVoiceCatalog } from "@/features/voice/model/use-voice";
import { Field } from "@/shared/ui/Field";
import { Slider } from "@/shared/ui/Slider";
import { Step } from "@/shared/ui/Step";

export function VoiceStep() {
  const voice = useVoice();
  const catalog = useVoiceCatalog();
  const production = useProduction();
  const { text } = useScript();
  const speakers = production.dialogue ? speakersIn(text) : [];

  /* Sin nota al lado del título: el desplegable ya dice qué voz está puesta. */
  return (
    <Step n={2} title="Voz">
      <Field id="voice" label={production.dialogue ? "Narrador" : "Locutor"}>
        <select id="voice" value={voice.id} onChange={(e) => voice.setId(e.target.value)}>
          {catalog.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label}
            </option>
          ))}
        </select>
      </Field>

      {production.dialogue &&
        (speakers.length ? (
          <div className="fields">
            {speakers.map((speaker) => (
              <Field key={speaker} id={`voice-${speaker}`} label={speaker}>
                <select
                  id={`voice-${speaker}`}
                  value={production.voices[speaker] ?? ""}
                  onChange={(e) => production.setVoice(speaker, e.target.value)}
                >
                  {catalog.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </Field>
            ))}
          </div>
        ) : (
          <p className="hint">
            Cada personaje aparece aquí en cuanto el guion tenga una línea que empiece con su nombre
            en mayúsculas («ANA: …»). Con el diálogo activado, el modelo del guion ya lo escribe así.
          </p>
        ))}

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
    </Step>
  );
}
