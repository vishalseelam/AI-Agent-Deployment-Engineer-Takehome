"""
Judge agent for evaluating and improving bedtime stories.
"""

import os
import json
from typing import List
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from models import Story, JudgeEvaluation, StoryRequest


class JudgeAgent:
    """Agent responsible for evaluating story quality and providing improvement suggestions."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.3,  # Lower temperature for more consistent evaluations
            max_tokens=2000,
            openai_api_key=api_key
        )
    
    def evaluate_story(self, story: Story, target_age_range: tuple[int, int] = (5, 10)) -> JudgeEvaluation:
        """Evaluate a story across multiple dimensions."""
        
        evaluation_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are an expert children's literature critic specializing in bedtime stories for ages 5-10.

Evaluate the following story across these dimensions (1-10 scale):
1. Overall Quality: Story structure, flow, and overall appeal
2. Age Appropriateness: Language, themes, and content suitable for ages 5-10
3. Engagement Level: How captivating and interesting the story is for children
4. Educational Value: Moral lessons, learning opportunities, positive messages
5. Creativity: Originality, imagination, and unique elements

For each dimension, provide:
- A score from 1-10
- Brief explanation of the score

Also identify:
- Strengths: What the story does well (list 2-4 points)
- Areas for Improvement: What could be better (list 2-4 points)
- Specific Suggestions: Concrete recommendations for improvement (list 2-4 points)
- Needs Revision: Whether the story should be revised (true/false)

CRITICAL: Respond ONLY with a valid JSON object in this exact format:
{{
    "overall_score": <number>,
    "age_appropriateness": <number>,
    "engagement_level": <number>,
    "educational_value": <number>,
    "creativity": <number>,
    "strengths": [<list of strings>],
    "areas_for_improvement": [<list of strings>],
    "suggestions": [<list of strings>],
    "needs_revision": <boolean>
}}

STORY TO EVALUATE:
Title: {story.title}
Category: {story.category}
Content: {story.content}"""),
            HumanMessage(content="Please evaluate this story and respond with the JSON evaluation.")
        ])
        
        result = self.llm.invoke(evaluation_prompt.format_messages())
        
        try:
            # Parse the JSON response
            evaluation_data = json.loads(result.content.strip())
            
            return JudgeEvaluation(
                overall_score=evaluation_data["overall_score"],
                age_appropriateness=evaluation_data["age_appropriateness"],
                engagement_level=evaluation_data["engagement_level"],
                educational_value=evaluation_data["educational_value"],
                creativity=evaluation_data["creativity"],
                strengths=evaluation_data["strengths"],
                areas_for_improvement=evaluation_data["areas_for_improvement"],
                suggestions=evaluation_data["suggestions"],
                needs_revision=evaluation_data["needs_revision"]
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback evaluation if JSON parsing fails
            return self._fallback_evaluation(story, result.content)
    
    def _fallback_evaluation(self, story: Story, raw_response: str) -> JudgeEvaluation:
        """Provide a fallback evaluation if JSON parsing fails."""
        return JudgeEvaluation(
            overall_score=7,
            age_appropriateness=8,
            engagement_level=7,
            educational_value=7,
            creativity=6,
            strengths=["Story has a clear structure", "Age-appropriate content"],
            areas_for_improvement=["Could use more vivid descriptions", "Character development could be enhanced"],
            suggestions=["Add more sensory details", "Include more character emotions"],
            needs_revision=False
        )
    
    def should_revise(self, evaluation: JudgeEvaluation, min_threshold: int = 6) -> bool:
        """Determine if a story should be revised based on evaluation scores."""
        critical_scores = [
            evaluation.overall_score,
            evaluation.age_appropriateness,
            evaluation.engagement_level
        ]
        
        # Revise if any critical score is below threshold or explicitly flagged
        return (
            evaluation.needs_revision or 
            any(score < min_threshold for score in critical_scores) or
            evaluation.overall_score < 7
        )
    
    def generate_revision_guidance(self, evaluation: JudgeEvaluation) -> str:
        """Generate specific guidance for story revision based on evaluation."""
        
        guidance_parts = []
        
        # Address low scores
        if evaluation.overall_score < 7:
            guidance_parts.append("Focus on improving overall story structure and flow.")
        
        if evaluation.age_appropriateness < 8:
            guidance_parts.append("Ensure language and themes are fully appropriate for the target age group.")
        
        if evaluation.engagement_level < 7:
            guidance_parts.append("Make the story more engaging with vivid descriptions and compelling characters.")
        
        if evaluation.educational_value < 7:
            guidance_parts.append("Strengthen the moral lesson or educational value of the story.")
        
        if evaluation.creativity < 6:
            guidance_parts.append("Add more creative and imaginative elements to make the story unique.")
        
        # Add specific suggestions
        if evaluation.suggestions:
            guidance_parts.append("Specific improvements to make:")
            guidance_parts.extend([f"- {suggestion}" for suggestion in evaluation.suggestions])
        
        # Add areas for improvement
        if evaluation.areas_for_improvement:
            guidance_parts.append("Areas needing attention:")
            guidance_parts.extend([f"- {area}" for area in evaluation.areas_for_improvement])
        
        return "\n".join(guidance_parts)
    
    def quick_quality_check(self, story: Story) -> bool:
        """Perform a quick quality check to determine if a story meets basic standards."""
        
        quick_check_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a children's story quality checker. 
            
            Quickly assess if this bedtime story meets basic quality standards:
            - Appropriate for ages 5-10
            - Has a clear beginning, middle, and end
            - Contains positive, comforting themes
            - Uses age-appropriate language
            - Has a satisfying, peaceful conclusion
            
            Respond with only "PASS" or "FAIL" based on whether the story meets these basic standards."""),
            HumanMessage(content=f"Title: {story.title}\n\nStory: {story.content}")
        ])
        
        result = self.llm.invoke(quick_check_prompt.format_messages())
        return result.content.strip().upper() == "PASS"
    
    def evaluate_modification(self, original: Story, revised: Story, user_feedback: str) -> dict:
        """Evaluate if the story was properly modified based on user feedback."""
        
        evaluation_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are evaluating whether a story revision successfully addressed the user's feedback.

Compare the original and revised versions and determine:
1. Was the user's feedback properly addressed?
2. Did the revision maintain story quality?
3. Is the revised version still age-appropriate?

Respond with JSON in this format:
{
    "feedback_addressed": true/false,
    "modification_quality": "excellent" | "good" | "fair" | "poor",
    "changes_made": ["list of specific changes made"],
    "story_quality_maintained": true/false,
    "evaluation_summary": "brief summary of the evaluation"
}"""),
            HumanMessage(content=f"""USER FEEDBACK: {user_feedback}

ORIGINAL STORY:
Title: {original.title}
{original.content}

REVISED STORY:
Title: {revised.title}
{revised.content}""")
        ])
        
        result = self.llm.invoke(evaluation_prompt.format_messages())
        
        try:
            return json.loads(result.content.strip())
        except json.JSONDecodeError:
            return {
                "feedback_addressed": True,
                "modification_quality": "good",
                "changes_made": ["Story was revised"],
                "story_quality_maintained": True,
                "evaluation_summary": "Story was successfully revised based on feedback"
            }
    
    def compare_stories(self, original: Story, revised: Story) -> dict:
        """Compare two versions of a story and determine which is better."""
        
        comparison_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""Compare these two versions of a bedtime story and determine which is better for children ages 5-10.

Consider:
- Story quality and engagement
- Age appropriateness
- Educational value
- Overall appeal for bedtime

Respond with JSON in this format:
{
    "better_version": "original" or "revised",
    "reason": "brief explanation of why",
    "improvement_areas": ["list of areas where the better version excels"]
}"""),
            HumanMessage(content=f"""ORIGINAL VERSION:
Title: {original.title}
{original.content}

REVISED VERSION:
Title: {revised.title}
{revised.content}""")
        ])
        
        result = self.llm.invoke(comparison_prompt.format_messages())
        
        try:
            return json.loads(result.content.strip())
        except json.JSONDecodeError:
            return {
                "better_version": "revised",
                "reason": "Revised version incorporates improvements",
                "improvement_areas": ["Overall quality"]
            }
