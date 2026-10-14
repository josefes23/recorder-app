"use client";

import { signed } from "@/domain/voice";
import { useVoice, useVoiceCatalog } from "@/features/voice/model/use-voice";
import { Field } from "@/shared/ui/Field";
import { Slider } from "@/shared/ui/Slider";
import { Step } from "@/shared/ui/Step";

export function VoiceStep() {
  const voice = useVoice();
  const catalog = useVoiceCatalog();

  /* Sin nota al lado del título: el desplegable ya dice qué voz está puesta. */
  return (
    <Step n={2} title="Voz">
      <Field id="voice" label="Locutor">
        <select id="voice" value={voice.id} onChange={(e) => voice.setId(e.target.value)}>
          {catalog.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label}
            </option>
          ))}
        </select>
      </Field>

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
