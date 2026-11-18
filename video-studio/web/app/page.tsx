"use client";

import { CaptionsStep } from "@/features/captions/ui/CaptionsStep";
import { DescriptionStep } from "@/features/description/ui/DescriptionStep";
import { GrowthStep } from "@/features/growth/ui/GrowthStep";
import { ImageSettingsPanel } from "@/features/illustrations/ui/ImageSettingsPanel";
import { LibraryPanel } from "@/features/library/ui/LibraryPanel";
import { SoundStep } from "@/features/production/ui/SoundStep";
import { OutputPanel } from "@/features/render/ui/OutputPanel";
import { ScenesStep } from "@/features/scenes/ui/ScenesStep";
import { ScriptStep } from "@/features/script/ui/ScriptStep";
import { StudioProvider } from "@/features/studio/model/studio-context";
import { JobsTray } from "@/features/studio/ui/JobsTray";
import { Topbar } from "@/features/studio/ui/Topbar";
import { VoiceStep } from "@/features/voice/ui/VoiceStep";
import { WriterSettings } from "@/features/writer/ui/WriterSettings";
import { httpGateway } from "@/infrastructure/http-gateway";
import { sseEventStream } from "@/infrastructure/sse-event-stream";
import { StepsProvider } from "@/shared/ui/steps";

/**
 * La ruta es la raíz de composición: elige la implementación del gateway y
 * ordena las features. Es el único punto del árbol que conoce `infrastructure`.
 */
export default function Page() {
  return (
    <StudioProvider gateway={httpGateway} events={sseEventStream}>
      <StepsProvider>
        <Topbar />

        <main className="workbench">
          {/* Los pasos en un solo panel: son una secuencia, no herramientas
              sueltas, y los filetes lo cuentan mejor que las cajas */}
          <div className="panel">
            <ScriptStep settings={<WriterSettings />} />
            <VoiceStep />
            <SoundStep />
            <CaptionsStep />
            <ScenesStep settings={<ImageSettingsPanel />} />
            <DescriptionStep />
            <GrowthStep />
          </div>

          <aside className="rail">
            <OutputPanel />
          </aside>
        </main>

        <LibraryPanel />
        <JobsTray />
      </StepsProvider>
    </StudioProvider>
  );
}
