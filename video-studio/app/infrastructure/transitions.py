"""
Pinta las transiciones (`domain.transition`): mezcla el fotograma del plano
que sale con el del que entra, y encadena los planos en una sola pista.

Solo trabaja durante los cambios: fuera de ellos cada fotograma es el del plano
que toca, tal cual, así que un video todo con cortes cuesta lo mismo que antes.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.transition import Blend, Change, look, moment

#: Un clip no se lee más allá de su último fotograma: algunos lectores de video
#: fallan o devuelven negro justo en `duration`.
_EDGE = 1e-3


def _rgb(frame):
    import numpy as np

    frame = np.asarray(frame)
    return frame[..., :3] if frame.ndim == 3 and frame.shape[2] > 3 else frame


def _zoomed(frame, scale: float):
    """El fotograma acercado `scale` veces sobre su centro, al mismo tamaño."""
    if scale <= 1.0001:
        return frame
    import numpy as np
    from PIL import Image

    h, w = frame.shape[:2]
    cw, ch = w / scale, h / scale
    box = ((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2)
    return np.asarray(Image.fromarray(frame).resize((w, h), Image.Resampling.BICUBIC, box=box))


def blend_frames(blend: Blend, outgoing, incoming):
    """El fotograma a mitad del cambio, del tamaño de los dos que mezcla."""
    import numpy as np

    lk = look(blend)
    a = _zoomed(_rgb(outgoing), lk.zoom_out)
    b = _zoomed(_rgb(incoming), lk.zoom_in)
    if lk.push is not None:
        # El que entra asoma por la derecha y empuja al otro hacia la izquierda.
        cut = round(lk.push * a.shape[1])
        return np.ascontiguousarray(np.concatenate([a[:, cut:], b[:, :cut]], axis=1))
    if lk.alpha <= 0 and lk.gain_out >= 1:
        return a
    if lk.alpha >= 1 and lk.gain_in >= 1:
        return b
    mixed = a.astype(np.float32) * (lk.gain_out * (1 - lk.alpha)) + b.astype(np.float32) * (lk.gain_in * lk.alpha)
    return np.clip(mixed + 0.5, 0, 255).astype(np.uint8)


def _local(clip, t: float) -> float:
    return min(max(t, 0.0), max(clip.duration - _EDGE, 0.0))


def chain(pieces: Sequence[tuple[float, object]], changes: Sequence[Change], duration: float):
    """
    Los planos en una sola pista. `pieces[i]` es (segundo en que empieza a
    pintarse, clip) y `changes[i]` el cambio del plano i al i + 1. Cada clip
    tiene que cubrir su tramo más la mitad de las transiciones de los lados
    (`domain.transition.reach`).
    """
    from moviepy import VideoClip

    if len(pieces) == 1:
        return pieces[0][1]

    def frame(t: float):
        i, blend = moment(changes, t)
        start, clip = pieces[i]
        current = clip.get_frame(_local(clip, t - start))
        if blend is None:
            return current
        nstart, nclip = pieces[i + 1]
        return blend_frames(blend, current, nclip.get_frame(_local(nclip, t - nstart)))

    return VideoClip(frame, duration=duration)
