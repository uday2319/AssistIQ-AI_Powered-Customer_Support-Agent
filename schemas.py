from pydantic import BaseModel
class supportResponse(BaseModel):
    answer: str
    category:str
    requires_human:bool