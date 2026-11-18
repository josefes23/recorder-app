"use client";

import { movableWords, startForWord } from "@/domain/narration";
import { useNarration, useScenes } from "@/features/scenes/model/use-scenes";

type Props = {
  thumbs: (string | null)[];
  selected: number;
  onSelect: (index: number) => void;
};

/**
 * El guion partido por escenas, en el orden en que se oye: cada trozo con la
 * imagen que se ve mientras se dice. Con una escena elegida, tocar una palabra
 * la hace entrar justo ahí; solo se pueden tocar las que no pisan a sus
 * vecinas. Es la forma directa de casar cada imagen con lo que se cuenta.
 */
export function SceneScript({ thumbs, selected, onSelect }: Props) {
  const scenes = useScenes();
  const narration = useNarration();
  const said = narration.scenes;
  const order = said.map((_, i) => i).sort((a, b) => said[a].from - said[b].from || a - b);
  const range = movableWords(said, selected, narration.tokens.length);

  return (
    <div className="scene-script">
      <p className="hint">
        {selected === 0
          ? "La escena 1 empieza siempre con la primera palabra. Elige otra para moverla."
          : range
            ? `Toca la palabra con la que quieres que entre la escena ${selected + 1}.`
            : `La escena ${selected + 1} no tiene sitio para moverse: sus vecinas están pegadas.`}
      </p>
      {order.map((i) => {
        const part = said[i];
        return (
          <section key={i} className={`script-block${i === selected ? " is-selected" : ""}`}>
            <button type="button" className="script-head" onClick={() => onSelect(i)} aria-pressed={i === selected}>
              {thumbs[i] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img className="scene-line-thumb" src={thumbs[i] ?? ""} alt="" />
              ) : (
                <span className="scene-line-thumb scene-thumb--empty" />
              )}
              <span className="num">{i + 1}</span>
              <span className="hint num">
                {part.start.toFixed(1)}–{part.end.toFixed(1)} s
              </span>
            </button>
            <p className="script-words">
              {part.to > part.from ? (
                narration.tokens.slice(part.from, part.to).map((word, offset) => {
                  const k = part.from + offset;
                  const movable = range !== null && k >= range[0] && k <= range[1];
                  return (
                    <span key={k}>
                      <span
                        className={`script-word${movable ? " is-movable" : ""}${i === selected && offset === 0 ? " is-start" : ""}`}
                        title={movable ? `Que la escena ${selected + 1} entre con «${word}»` : undefined}
                        onClick={movable ? () => scenes.setStart(selected, startForWord(k)) : undefined}
                      >
                        {word}
                      </span>{" "}
                    </span>
                  );
                })
              ) : (
                <span className="hint">Entra después de que acabe la voz: no se verá.</span>
              )}
            </p>
          </section>
        );
      })}
    </div>
  );
}
