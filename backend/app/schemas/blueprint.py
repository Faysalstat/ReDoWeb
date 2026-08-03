from pydantic import BaseModel


class ColorPalette(BaseModel):
    primary: str
    secondary: str
    accent: str


class Fonts(BaseModel):
    heading: str
    body: str


class Frontmatter(BaseModel):
    site_name: str
    colors: ColorPalette
    logo: str | None = None
    fonts: Fonts
    tone: str | None = None


class BlueprintResponse(BaseModel):
    project_id: str
    design_md_path: str
    frontmatter: Frontmatter
    design_md: str
