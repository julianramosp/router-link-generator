# Pydantic models for requests and responses

from pydantic import BaseModel
from typing import List

class RouteRequest(BaseModel):
    file_path: str

class RouteResponse(BaseModel):
    addresses: List[str]
    google_maps_link: str
