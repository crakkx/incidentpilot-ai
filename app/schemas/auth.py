from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreateRequest(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(viewer|operator|admin)$")


class ApiKeyCreateResponse(BaseModel):
    email: str
    role: str
    api_key: str = Field(
        description="Plaintext API key — shown once, not recoverable afterwards."
    )
