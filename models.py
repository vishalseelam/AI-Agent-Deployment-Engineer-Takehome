"""
Pydantic models for the bedtime story generator system.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


class StoryCategory(str, Enum):
    """Categories for different types of bedtime stories."""
    ADVENTURE = "adventure"
    FRIENDSHIP = "friendship"
    MAGICAL = "magical"
    ANIMAL = "animal"
    EDUCATIONAL = "educational"
    MYSTERY = "mystery"
    FAMILY = "family"


class StoryRequest(BaseModel):
    """Model for user's story request."""
    request: str = Field(description="The user's story request")
    age_range: tuple[int, int] = Field(default=(5, 10), description="Target age range")
    length_preference: Literal["short", "medium", "long"] = Field(default="medium")
    category: Optional[StoryCategory] = Field(default=None, description="Auto-detected story category")


class Story(BaseModel):
    """Model for generated stories."""
    title: str = Field(description="Story title")
    content: str = Field(description="Full story content")
    category: StoryCategory = Field(description="Story category")
    age_appropriate: bool = Field(description="Whether story is age-appropriate")
    moral_lesson: Optional[str] = Field(default=None, description="Moral or lesson of the story")
    characters: List[str] = Field(default_factory=list, description="Main characters in the story")


class JudgeEvaluation(BaseModel):
    """Model for judge's evaluation of a story."""
    overall_score: int = Field(ge=1, le=10, description="Overall story quality score")
    age_appropriateness: int = Field(ge=1, le=10, description="Age appropriateness score")
    engagement_level: int = Field(ge=1, le=10, description="How engaging the story is")
    educational_value: int = Field(ge=1, le=10, description="Educational or moral value")
    creativity: int = Field(ge=1, le=10, description="Creativity and originality")
    
    strengths: List[str] = Field(description="What the story does well")
    areas_for_improvement: List[str] = Field(description="Areas that could be improved")
    suggestions: List[str] = Field(description="Specific suggestions for improvement")
    
    needs_revision: bool = Field(description="Whether the story needs to be revised")


class UserFeedback(BaseModel):
    """Model for user feedback on stories."""
    feedback_type: Literal["story_modification", "general_chat"] = Field(description="Type of feedback")
    content: str = Field(description="Feedback content")
    specific_changes: Optional[List[str]] = Field(default=None, description="Specific changes requested")


class ConversationState(BaseModel):
    """Model for tracking conversation state."""
    current_story: Optional[Story] = Field(default=None)
    story_history: List[Story] = Field(default_factory=list)
    feedback_history: List[UserFeedback] = Field(default_factory=list)
    revision_count: int = Field(default=0)
    user_preferences: dict = Field(default_factory=dict)
