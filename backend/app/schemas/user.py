from pydantic import BaseModel


class UserMeResponse(BaseModel):
    user_id: int
    username: str
    tts_voice: str | None = None
    tts_rate: str | None = None


class UpdatePreferencesRequest(BaseModel):
    tts_voice: str | None = None
    tts_rate: str | None = None
