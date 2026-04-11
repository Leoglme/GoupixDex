from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    margin_percent: int


class SettingsUpdate(BaseModel):
    margin_percent: int = Field(ge=0, le=500)
