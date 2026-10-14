import type { NextConfig } from "next";

/**
 * Dos modos:
 *
 * - `npm run dev` — servidor de Next en :3000. Las llamadas a /api se reescriben
 *   hacia FastAPI en :8000, así que el navegador nunca cruza de origen y no hace
 *   falta configurar CORS.
 *
 * - `npm run export` — build estático a web/out, que sirve el propio FastAPI.
 *   Ahí interfaz y API comparten origen y las reescrituras sobran (Next las
 *   ignora en modo export, de ahí que solo se declaren fuera de él).
 */
const isExport = process.env.NEXT_EXPORT === "1";
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = isExport
  ? { output: "export", images: { unoptimized: true } }
  : {
      /**
       * El proxy de desarrollo corta las reescrituras a los 30 s. Eso mataba el
       * flujo de eventos, que es una respuesta abierta a propósito. Se sube a
       * una hora: en el build exportado no hay proxy, así que esto solo afecta
       * a `npm run dev`.
       */
      experimental: { proxyTimeout: 60 * 60 * 1000 },
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
      },
    };

export default nextConfig;
