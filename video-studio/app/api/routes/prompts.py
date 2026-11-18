from fastapi import APIRouter

from app.api.deps import StudioDep
from app.api.schemas import PromptPreviewRequest, PromptRequest

router = APIRouter(prefix="/api", tags=["prompts"])


@router.get("/prompts")
def prompts(studio: StudioDep) -> dict:
    """Todos los prompts, con su texto actual, el original y un ejemplo montado."""
    return {"prompts": studio.prompts.catalog()}


@router.put("/prompts/{prompt_id}")
def save_prompt(prompt_id: str, req: PromptRequest, studio: StudioDep) -> dict:
    return studio.prompts.save(prompt_id, req.text)


@router.delete("/prompts/{prompt_id}")
def reset_prompt(prompt_id: str, studio: StudioDep) -> dict:
    """Vuelve al original."""
    return studio.prompts.reset(prompt_id)


@router.post("/prompts/{prompt_id}/preview")
def preview_prompt(prompt_id: str, req: PromptPreviewRequest, studio: StudioDep) -> dict:
    """El prompt montado con una edición aún sin guardar."""
    return studio.prompts.preview(prompt_id, req.text)
