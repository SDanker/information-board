from pydantic import BaseModel, Field

from .content_schemas import PublicationWindow


class EmergencySection(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=2000)


class EmergencyCreate(PublicationWindow):
    title: str = Field(min_length=2, max_length=200)
    address: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=4000)
    sections: list[EmergencySection] = Field(default_factory=list)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EmergencyUpdate(PublicationWindow):
    """Editable texts of a featured event; omitted fields keep their current value."""

    title: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    sections: list[EmergencySection] | None = None


class EmergencyLocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ActiveEmergencyResponse(BaseModel):
    active: bool
    content_id: str | None = None
    title: str | None = None
