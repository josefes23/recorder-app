"use client";

import { useWriter } from "@/features/writer/model/use-writer";

import { StepNav } from "./StepNav";

export function Topbar() {
  const { settings, label } = useWriter();

  return (
    <header className="topbar">
      <h1 className="brand">video&#8209;studio</h1>
      <StepNav />
      <span className={`chip topbar-model${label ? " is-on" : ""}`}>
        {settings ? (label ?? "Sin modelo · guion manual") : "…"}
      </span>
    </header>
  );
}
