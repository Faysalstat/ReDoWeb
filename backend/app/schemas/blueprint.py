from pydantic import BaseModel

from ..ai.blueprint_schema import BlueprintDocument


class BlueprintResponse(BaseModel):
    project_id: str
    version: int
    scraped_json_path: str
    blueprint_json_path: str
    design_md_path: str
    blueprint: BlueprintDocument
    usage: dict
