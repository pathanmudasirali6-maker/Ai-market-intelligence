from pydantic import BaseModel

class SearchQuery(BaseModel):
    q: str
