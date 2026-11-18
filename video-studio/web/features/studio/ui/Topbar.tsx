"use client";

import { useState } from "react";

import { PromptsPanel } from "@/features/prompts/ui/PromptsPanel";
import { useWriter } from "@/features/writer/model/use-writer";

import { useFreshStart } from "../model/use-fresh-start";

import { StepNav } from "./StepNav";

export function Topbar() {
  const { settings, label } = useWriter();
  const [prompts, showPrompts] = useState(false);
  const { startOver } = useFreshStart();

  return (
    <header className="topbar">
      <h1 className="brand">video&#8209;studio</h1>
      <StepNav />
      <span className={`chip topbar-model${label ? " is-on" : ""}`}>
        {settings ? (label ?? "Sin modelo · guion manual") : "…"}
      </span>
      <button className="btn btn--sm" onClick={() => void startOver()} title="Deja todos los pasos en blanco">
        Nuevo video
      </button>
      <button className="btn btn--sm" onClick={() => showPrompts(true)}>
        Prompts
      </button>
      {prompts && <PromptsPanel onClose={() => showPrompts(false)} />}
    </header>
  );
}
