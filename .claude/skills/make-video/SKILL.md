---
name: make-video
description: Genera un Reel/Short vertical (9:16, 1080x1920) con voz en español y subtítulos sincronizados a partir de un tema. Úsala cuando el usuario escriba "/make-video [TEMA]", pida "hazme un video/reel/short sobre X", o quiera convertir una idea en un video corto para Instagram, TikTok o YouTube Shorts.
---

# make-video

La skill completa está en `auto-video-generator/.claude/skills/make-video/SKILL.md`.
Lee ese archivo con Read antes de nada y sigue sus instrucciones tal cual.

Este archivo solo existe para que `/make-video` funcione desde la raíz del
monorepo. Antes era un symlink, pero Git en Windows no los recrea sin el Modo de
desarrollador; un archivo real anda igual en Mac, Linux y Windows. Si cambias la
descripción de la skill original, cámbiala también aquí.
