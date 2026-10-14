"use client";

import { Field } from "./Field";

type Props = {
  id: string;
  label: string;
  value: number;
  /** Cómo se escribe el valor si no basta el número pelado: «+8 %», «0,52». */
  display?: string;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
};

export function Slider({ id, label, value, display, min, max, step = 1, onChange }: Props) {
  return (
    <Field id={id} label={label} value={display ?? value}>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </Field>
  );
}
