import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "video-studio",
  description: "Generador local de Reels verticales con voz en español",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
