"use client";

import { useRef, useState } from "react";

import { useBackgrounds } from "@/features/backgrounds/model/use-backgrounds";
import { useStatus } from "@/features/studio/model/use-studio-actions";

type Props = {
  /** Qué hacer con el fondo elegido lo decide quien abre el diálogo. */
  onSelect: (name: string) => void;
  onClose: () => void;
};

export function BackgroundPicker({ onSelect, onClose }: Props) {
  const backgrounds = useBackgrounds();
  const { busy } = useStatus();
  const [query, setQuery] = useState("");
  const [log, setLog] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const working = busy === "backgrounds";

  const download = async () => {
    setLog("Descargando de Pexels…");
    setLog((await backgrounds.download(query)) ?? "");
  };

  const upload = async (file: File) => {
    setLog("Subiendo…");
    await backgrounds.upload(file);
    setLog("Subido.");
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="spread">
          <h2 className="panel-title">Elegir fondo</h2>
          <button className="btn btn--sm" onClick={onClose}>
            Cerrar
          </button>
        </div>

        <div className="cluster cluster--search">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && download()}
            placeholder="Buscar en Pexels: sleeping bedroom, coffee…"
            autoComplete="off"
          />
          <button className="btn" onClick={download} disabled={working}>
            Descargar
          </button>
          <label className="btn">
            Subir archivo
            <input
              ref={fileRef}
              type="file"
              accept="video/*,image/*"
              hidden
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
          </label>
        </div>

        {log && <p className="hint">{log}</p>}

        <div className="gallery">
          {backgrounds.items.length === 0 ? (
            <p className="hint">No hay fondos todavía. Busca en Pexels o sube un archivo.</p>
          ) : (
            backgrounds.items.map((bg) => (
              <figure key={bg.name} onClick={() => onSelect(bg.name)}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={backgrounds.thumbUrl(bg.thumb)} alt="" loading="lazy" />
                <figcaption>
                  {bg.group}
                  {bg.duration ? ` · ${bg.duration}s` : ""}
                </figcaption>
              </figure>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
