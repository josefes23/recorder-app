"use client";

import { useWriter } from "@/features/writer/model/use-writer";

export function Topbar() {
  const { settings, label } = useWriter();

  return (
    <header className="topbar">
      <h1 className="brand">video&#8209;studio</h1>
      <span className={`chip${label ? " is-on" : ""}`}>
        {settings ? (label ?? "Sin modelo · guion manual") : "…"}
      </span>
    </header>
  );
}
