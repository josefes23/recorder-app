/**
 * Estilo de los subtítulos.
 *
 * Los nombres en snake_case son los del motor (`generate.py`) y viajan intactos
 * hasta el render y hasta el historial. Aquí no son un resto del transporte:
 * son el vocabulario del dominio, y renombrarlos obligaría a traducir en las
 * dos direcciones sin ganar nada.
 */
export type Style = {
  font_size: number;
  stroke: number;
  y_ratio: number;
  max_chars: number;
  max_lines: number;
  animate: boolean;
};

export const DEFAULT_STYLE: Style = {
  font_size: 92,
  stroke: 8,
  y_ratio: 0.52,
  max_chars: 30,
  max_lines: 3,
  animate: true,
};
