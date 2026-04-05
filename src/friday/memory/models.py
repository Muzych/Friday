from pydantic import BaseModel, Field


class SessionMemoryDelta(BaseModel):
    goal: str = ""
    active_tasks: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recent_decisions: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    summary: str = ""


class DeepMemoryDelta(BaseModel):
    profile_facts: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    long_running_projects: list[str] = Field(default_factory=list)
    stable_workflows: list[str] = Field(default_factory=list)


class SessionMemorySnapshot(BaseModel):
    session_id: str
    revision: int = 0
    summary: str = ""
    goal: str = ""
    active_tasks: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recent_decisions: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    last_anchor_id: str | None = None


class DeepMemorySnapshot(BaseModel):
    actor_key: str
    revision: int = 0
    profile_facts: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    long_running_projects: list[str] = Field(default_factory=list)
    stable_workflows: list[str] = Field(default_factory=list)
    last_anchor_id: str | None = None


class RenderableMemoryContext(BaseModel):
    session_snapshot: SessionMemorySnapshot
    deep_snapshot: DeepMemorySnapshot | None = None
    rendered_prompt: str = ""


class MemoryUpdateResult(BaseModel):
    session_snapshot: SessionMemorySnapshot
    deep_snapshot: DeepMemorySnapshot | None = None
    processed_entry_count: int = 0
