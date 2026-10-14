import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

/**
 * La regla de dependencia, vigilada por el linter.
 *
 * Las capas apuntan hacia dentro: `domain` no conoce a nadie, `application`
 * solo conoce al dominio, y las features hablan con casos de uso a través de
 * puertos. La implementación HTTP solo la toca la ruta, que es la raíz de
 * composición. Sin esto la arquitectura duraría hasta el primer atajo.
 */
const forbid = (files, groups, message) => ({
  files,
  rules: {
    "no-restricted-imports": ["error", { patterns: [{ group: groups, message }] }],
  },
});

const REACT = ["react", "react-dom", "next", "next/*"];

const layers = [
  forbid(
    ["domain/**"],
    ["@/application/*", "@/infrastructure/*", "@/features/*", "@/shared/*", ...REACT],
    "El dominio son reglas puras: no conoce casos de uso, transporte ni React.",
  ),
  forbid(
    ["application/**"],
    ["@/infrastructure/*", "@/features/*", "@/shared/*", ...REACT],
    "Los casos de uso hablan con el puerto StudioGateway, no con su implementación ni con la interfaz.",
  ),
  forbid(
    ["infrastructure/**"],
    ["@/features/*", "@/shared/*"],
    "Un adaptador implementa un puerto; no sabe qué interfaz lo usa.",
  ),
  forbid(
    ["features/**"],
    ["@/infrastructure/*"],
    "Las features reciben el gateway por inyección: quien elige la implementación es la ruta.",
  ),
  forbid(
    ["shared/**"],
    ["@/domain/*", "@/application/*", "@/infrastructure/*", "@/features/*"],
    "Lo compartido es presentación tonta: recibe todo por props.",
  ),
];

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  ...layers,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
