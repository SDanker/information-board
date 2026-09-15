from pydantic import BaseModel, Field


class EmergencySection(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=2000)


class EmergencyCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    address: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=4000)
    sections: list[EmergencySection] = Field(default_factory=list)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EmergencyLocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ActiveEmergencyResponse(BaseModel):
    active: bool
    content_id: str | None = None
    title: str | None = None
