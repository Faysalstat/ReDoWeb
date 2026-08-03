from pydantic import BaseModel, HttpUrl


class CrawlRequest(BaseModel):
    url: HttpUrl
    tos_accepted: bool = False


class PageRecord(BaseModel):
    url: str
    http_status: int
    storage_path: str


class AssetRecord(BaseModel):
    original_url: str
    asset_type: str
    storage_path: str
    content_type: str | None = None


class CrawlResponse(BaseModel):
    project_id: str
    source_url: str
    page_count: int
    pages: list[PageRecord]
    assets: list[AssetRecord]
