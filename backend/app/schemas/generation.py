from pydantic import BaseModel


class GenerationResponse(BaseModel):
    project_id: str
    tier: str
    postprocess: dict
    template_used: str
    output_dir: str
    files: list[str]
    summary: str
    usage: dict
    iterations: int
