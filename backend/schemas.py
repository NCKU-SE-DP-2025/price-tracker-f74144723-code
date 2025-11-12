from pydantic import BaseModel

# Auth Schemas
class UserAuthSchema(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    username: str

# News Schemas
class PromptRequest(BaseModel):
    prompt: str

class NewsSummaryRequest(BaseModel):
    content: str

class NewsResponse(BaseModel):
    id: int
    url: str
    title: str
    time: str
    content: str
    summary: str
    reason: str
    upvotes: int = 0
    is_upvoted: bool = False