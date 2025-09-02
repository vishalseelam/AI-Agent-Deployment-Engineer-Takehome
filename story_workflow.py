"""
LangGraph workflow for the bedtime story generation system.
"""

import os
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage

from models import StoryRequest, Story, JudgeEvaluation, UserFeedback, ConversationState
from storyteller import StorytellerAgent
from judge import JudgeAgent


class WorkflowState(TypedDict):
    """State for the story generation workflow."""
    story_request: Optional[StoryRequest]
    current_story: Optional[Story]
    evaluation: Optional[JudgeEvaluation]
    user_feedback: Optional[str]
    revision_count: int
    conversation_state: ConversationState
    should_continue: bool
    final_story: Optional[Story]


class StoryWorkflow:
    """LangGraph-based workflow for story generation and refinement."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        
        self.storyteller = StorytellerAgent()
        self.judge = JudgeAgent()
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.3,
            openai_api_key=api_key
        )
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("generate_story", self._generate_story)
        workflow.add_node("evaluate_story", self._evaluate_story)
        workflow.add_node("process_feedback", self._process_feedback)
        workflow.add_node("revise_story", self._revise_story)
        workflow.add_node("finalize_story", self._finalize_story)
        
        # Add edges
        workflow.set_entry_point("generate_story")
        workflow.add_edge("generate_story", "evaluate_story")
        
        # Conditional edges based on evaluation
        workflow.add_conditional_edges(
            "evaluate_story",
            self._should_revise,
            {
                "revise": "revise_story",
                "finalize": "finalize_story"
            }
        )
        
        workflow.add_edge("revise_story", "evaluate_story")
        workflow.add_edge("process_feedback", "revise_story")
        workflow.add_edge("finalize_story", END)
        
        return workflow.compile()
    
    def _generate_story(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate initial story."""
        story = self.storyteller.generate_story(state["story_request"])
        
        return {
            **state,
            "current_story": story,
            "revision_count": 0
        }
    
    def _evaluate_story(self, state: WorkflowState) -> Dict[str, Any]:
        """Evaluate the current story."""
        evaluation = self.judge.evaluate_story(
            state["current_story"]
        )
        
        return {
            **state,
            "evaluation": evaluation
        }
    
    def _should_revise(self, state: WorkflowState) -> str:
        """Determine if story should be revised based on evaluation."""
        evaluation = state["evaluation"]
        revision_count = state["revision_count"]
        
        # Don't revise more than 2 times to avoid infinite loops
        if revision_count >= 2:
            return "finalize"
        
        # Check if revision is needed based on judge evaluation
        if self.judge.should_revise(evaluation):
            return "revise"
        
        return "finalize"
    
    def _process_feedback(self, state: WorkflowState) -> Dict[str, Any]:
        """Process user feedback for story revision."""
        feedback = state["user_feedback"]
        
        # Classify feedback type
        feedback_type = self._classify_feedback(feedback)
        
        # Update conversation state
        conversation_state = state["conversation_state"]
        user_feedback = UserFeedback(
            feedback_type=feedback_type,
            content=feedback
        )
        conversation_state.feedback_history.append(user_feedback)
        
        return {
            **state,
            "conversation_state": conversation_state
        }
    
    def _classify_feedback(self, feedback: str) -> str:
        """Classify user feedback as story modification or general chat."""
        classification_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""Classify this user feedback into one of these categories:

            "story_modification": User wants to modify the current story in any way such as:
            - Make it longer or shorter
            - Change characters, plot, or setting
            - Adjust tone or mood
            - Add or remove elements
            - Any other story changes
            
            "general_chat": User is having a general conversation such as:
            - Asking questions about stories in general
            - Casual conversation
            - Compliments or general comments
            - Questions unrelated to modifying the current story
            
            Respond with only the category name."""),
            HumanMessage(content=feedback)
        ])
        
        result = self.llm.invoke(classification_prompt.format_messages())
        classification = result.content.strip().lower()
        
        if classification in ["story_modification", "general_chat"]:
            return classification
        return "story_modification"  # Default to modification for safety
    
    def _revise_story(self, state: WorkflowState) -> Dict[str, Any]:
        """Revise story based on evaluation or user feedback."""
        current_story = state["current_story"]
        evaluation = state["evaluation"]
        user_feedback = state.get("user_feedback")
        
        # Determine revision guidance
        if user_feedback:
            # User feedback takes priority
            revision_guidance = f"User feedback: {user_feedback}"
        else:
            # Use judge evaluation
            revision_guidance = self.judge.generate_revision_guidance(evaluation)
        
        # Revise the story
        revised_story = self.storyteller.revise_story(current_story, revision_guidance)
        
        # Update conversation state
        conversation_state = state["conversation_state"]
        conversation_state.story_history.append(current_story)
        conversation_state.revision_count += 1
        
        return {
            **state,
            "current_story": revised_story,
            "revision_count": state["revision_count"] + 1,
            "conversation_state": conversation_state,
            "user_feedback": None  # Clear feedback after processing
        }
    
    def _finalize_story(self, state: WorkflowState) -> Dict[str, Any]:
        """Finalize the story."""
        final_story = state["current_story"]
        
        # Update conversation state
        conversation_state = state["conversation_state"]
        conversation_state.current_story = final_story
        
        return {
            **state,
            "final_story": final_story,
            "conversation_state": conversation_state,
            "should_continue": False
        }
    
    def generate_story(self, request: str, length_preference: str = "medium") -> Story:
        """Generate a complete story through the workflow."""
        
        story_request = StoryRequest(
            request=request,
            age_range=(5, 10),  # Fixed age range as per instructions
            length_preference=length_preference
        )
        
        initial_state = WorkflowState(
            story_request=story_request,
            current_story=None,
            evaluation=None,
            user_feedback=None,
            revision_count=0,
            conversation_state=ConversationState(),
            should_continue=True,
            final_story=None
        )
        
        # Run the workflow
        result = self.workflow.invoke(initial_state)
        return result["final_story"]
    
    def handle_general_chat(self, feedback: str, current_story: Optional[Story] = None) -> str:
        """Handle general chat requests."""
        context = ""
        if current_story:
            context = f"\n\nCurrent story context:\nTitle: {current_story.title}\nCategory: {current_story.category}"
        
        chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are a friendly bedtime story assistant. The user is having a casual conversation with you. 
            
            Respond naturally and helpfully. Keep responses concise and warm.{context}
            
            If they ask about the current story, reference it appropriately. If they're just chatting, engage in friendly conversation."""),
            HumanMessage(content=feedback)
        ])
        
        result = self.llm.invoke(chat_prompt.format_messages())
        return result.content.strip()
    
    def process_user_feedback(self, story: Story, feedback: str, 
                            conversation_state: ConversationState) -> tuple[Optional[Story], Optional[str], str]:
        """Process user feedback and return (revised_story, chat_response, feedback_type)."""
        
        # Classify the feedback
        feedback_type = self._classify_feedback(feedback)
        
        if feedback_type == "general_chat":
            chat_response = self.handle_general_chat(feedback, story)
            return None, chat_response, feedback_type
        
        else:  # story_modification
            # Store original story for comparison
            original_story = story
            
            # Revise the story
            revised_story = self.storyteller.revise_story(story, feedback)
            
            # Evaluate the modification
            modification_eval = self.judge.evaluate_modification(original_story, revised_story, feedback)
            
            # Update conversation state
            conversation_state.story_history.append(original_story)
            conversation_state.revision_count += 1
            conversation_state.current_story = revised_story
            
            return revised_story, None, feedback_type


class FeedbackProcessor:
    """Helper class for processing different types of user feedback."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.3,
            openai_api_key=api_key
        )
    
    def extract_specific_changes(self, feedback: str) -> List[str]:
        """Extract specific change requests from user feedback."""
        extraction_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""Extract specific change requests from this user feedback about a bedtime story.
            
            Return a list of specific, actionable changes the user wants. If no specific changes are mentioned, return an empty list.
            
            Format your response as a simple list, one change per line, starting with "-"."""),
            HumanMessage(content=feedback)
        ])
        
        result = self.llm.invoke(extraction_prompt.format_messages())
        
        # Parse the response into a list
        changes = []
        for line in result.content.strip().split('\n'):
            line = line.strip()
            if line.startswith('-'):
                changes.append(line[1:].strip())
        
        return changes
    
    def interpret_vague_feedback(self, feedback: str, story: Story) -> str:
        """Interpret vague feedback and provide specific revision guidance."""
        interpretation_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""The user provided this feedback about a bedtime story: "{feedback}"
            
            The story is titled "{story.title}" and is about: {story.content[:200]}...
            
            Interpret this feedback and provide specific, actionable revision guidance for improving the story.
            Focus on concrete changes that would address the user's concerns."""),
            HumanMessage(content="Please provide specific revision guidance based on this feedback.")
        ])
        
        result = self.llm.invoke(interpretation_prompt.format_messages())
        return result.content.strip()
