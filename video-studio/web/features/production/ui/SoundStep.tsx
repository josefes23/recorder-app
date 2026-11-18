"use client";

import { useRef } from "react";

import { MUSIC_ACCEPT } from "@/domain/music";
import { useMusic, useProduction } from "@/features/production/model/use-production";
import { useStatus } from "@/features/studio/model/use-studio-actions";
import { ActionError } from "@/features/studio/ui/ActionError";
import { Field } from "@/shared/ui/Field";
import { Help } from "@/shared/ui/Help";
import { Slider } from "@/shared/ui/Slider";
import { Step } from "@/shared/ui/Step";

/**
 * La música de fondo sale de una galería propia: pistas que sube el usuario,
 * de bibliotecas libres de derechos. Al renderizar baja sola bajo la voz.
 */
export function SoundStep() {
  const production = useProduction();
  const music = useMusic();
  const { busy } = useStatus();
  const picker = useRef<HTMLInputElement>(null);

  const chosen = music.tracks.find((t) => t.name === production.music);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    const name = await music.upload(file);
    if (name) production.setMusic(name);
    if (picker.current) picker.current.value = "";
  };

  const remove = async (name: string) => {
    if (await music.remove(name)) production.setMusic("");
  };

  return (
    <Step n={3} title="Música y sonido" note={chosen ? chosen.name : "solo la voz"}>
      <Field id="music" label="Música de fondo">
        <select id="music" value={production.music} onChange={(e) => production.setMusic(e.target.value)}>
          <option value="">Sin música</option>
          {music.tracks.map((t) => (
            <option key={t.name} value={t.name}>
              {t.name} · {Math.round(t.duration)} s
            </option>
          ))}
        </select>
      </Field>

      {chosen && (
        <>
          <audio className="music-player" controls preload="none" src={music.url(chosen.name)} />
          <Slider
            id="music-volume"
            label="Volumen en los silencios"
            value={Math.round(production.musicVolume * 100)}
            display={`${Math.round(production.musicVolume * 100)} %`}
            min={5}
            max={60}
            step={5}
            onChange={(v) => production.setMusicVolume(v / 100)}
          />
          <div className="spread">
            <span className="hint">Baja sola mientras alguien habla</span>
            <Help label="Cómo suena la música">
              Se repite hasta cubrir el video, entra y sale con un fundido y baja sola mientras
              alguien habla.
            </Help>
          </div>
        </>
      )}

      <div className="cluster">
        <button className="btn" disabled={busy === "music"} onClick={() => picker.current?.click()}>
          {busy === "music" ? "Subiendo…" : "Subir una pista"}
        </button>
        {chosen && (
          <button className="btn" disabled={busy === "music"} onClick={() => remove(chosen.name)}>
            Borrar de la galería
          </button>
        )}
        <input
          ref={picker}
          type="file"
          accept={MUSIC_ACCEPT}
          hidden
          onChange={(e) => upload(e.target.files?.[0])}
        />
      </div>
      <ActionError place="sound" />
      <div className="spread">
        <span className="hint">MP3, M4A, WAV u OGG</span>
        <Help label="Qué música usar">
          Usa música libre de derechos (la biblioteca de audio de YouTube, Pixabay Music): MP3, M4A,
          WAV u OGG.
        </Help>
      </div>

      <label className="cluster check" htmlFor="ambient">
        <input
          id="ambient"
          type="checkbox"
          checked={production.ambient}
          onChange={(e) => production.setAmbient(e.target.checked)}
        />
        <span className="hint">
          Mezclar debajo de la voz el sonido de los clips: los animados con IA traen sonido ambiente;
          los de Pexels casi nunca.
        </span>
      </label>
    </Step>
  );
}
