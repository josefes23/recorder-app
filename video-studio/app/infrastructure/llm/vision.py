"""Una imagen lista para enseñársela a un modelo de texto."""

from __future__ import annotations

import base64
import io

from app.domain.illustration import GeneratedImage

#: Lado largo por encima del cual Anthropic reescala la imagen por su cuenta, y
#: tope de peso: rechaza las de más de 5 MB. Las de Cloudflare (864x1536, JPEG)
#: pasan tal cual; las de Nano Banana a 2K se reducen aquí.
MAX_SIDE = 1568
MAX_BYTES = 4_500_000


def fit(image: GeneratedImage) -> tuple[bytes, str]:
    """Los bytes y su tipo, reducidos solo si hace falta."""
    from PIL import Image

    with Image.open(io.BytesIO(image.data)) as picture:
        if max(picture.size) <= MAX_SIDE and len(image.data) <= MAX_BYTES:
            return image.data, image.media_type
        picture.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        picture.convert("RGB").save(out, "JPEG", quality=90)
        return out.getvalue(), "image/jpeg"


def as_base64(image: GeneratedImage) -> tuple[str, str]:
    data, media_type = fit(image)
    return base64.standard_b64encode(data).decode("ascii"), media_type
