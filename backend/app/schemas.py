from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    conversation_id: str | None = Field(default=None, description="Optional conversation ID to continue a chat")


class SourceItem(BaseModel):
    filename: str
    page: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class AnalysisFactors(BaseModel):
    isInfoSystemUsed: bool = False
    hasFinancialLoss: bool = False
    hasDeception: bool = False


class AnalyzeRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=8192)
    factors: AnalysisFactors | None = None


# ── Conversation Schemas ─────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: str = Field(default="Yeni Sohbet", max_length=200)


class ConversationOut(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


class SaveMessageRequest(BaseModel):
    conversation_id: str
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
