from pydantic import BaseModel
from typing import Optional


class RunCreate(BaseModel):
    project_path: str
    prompt: str
    fast_model: Optional[str] = None
    deep_model: Optional[str] = None


class RunResponse(BaseModel):
    id: int
    status: str


class AcceptChangeRequest(BaseModel):
    accepted: bool
