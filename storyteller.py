"""
Storyteller agent for generating age-appropriate bedtime stories.
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from models import StoryRequest, Story, StoryCategory


class StorytellerAgent:
    """Agent responsible for generating bedtime stories."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=3000,
            openai_api_key=api_key
        )
        
    def categorize_request(self, request: str) -> StoryCategory:
        """Categorize the story request to apply appropriate generation strategy."""
        categorization_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a story categorization expert. Based on the user's request, 
            categorize it into one of these categories:
            - adventure: stories involving journeys, quests, or exciting experiences
            - friendship: stories about relationships, cooperation, and social bonds
            - magical: stories with fantasy elements, magic, or supernatural themes
            - animal: stories primarily featuring animals as main characters
            - educational: stories that teach concepts, facts, or skills
            - mystery: stories involving puzzles, secrets, or problem-solving
            - family: stories about family relationships and dynamics
            
            Respond with only the category name in lowercase."""),
            HumanMessage(content=f"Categorize this story request: {request}")
        ])
        
        result = self.llm.invoke(categorization_prompt.format_messages())
        try:
            return StoryCategory(result.content.strip().lower())
        except ValueError:
            return StoryCategory.ADVENTURE  # Default fallback
    
    def _get_category_specific_prompt(self, category: StoryCategory) -> str:
        """Get category-specific storytelling guidelines."""
        prompts = {
            StoryCategory.ADVENTURE: """
            Focus on exciting journeys and discoveries. Include:
            - A clear quest or goal for the protagonist
            - Obstacles that require courage and creativity to overcome
            - A sense of wonder and exploration
            - Positive resolution that rewards bravery and persistence
            """,
            StoryCategory.FRIENDSHIP: """
            Emphasize relationships and social connections. Include:
            - Characters learning to work together
            - Themes of kindness, empathy, and understanding
            - Conflict resolution through communication
            - The value of helping others and being a good friend
            """,
            StoryCategory.MAGICAL: """
            Create wonder through fantasy elements. Include:
            - Magical creatures or powers used responsibly
            - Enchanted settings that spark imagination
            - Magic that comes with lessons about responsibility
            - Wonder and awe balanced with gentle life lessons
            """,
            StoryCategory.ANIMAL: """
            Feature animal characters with relatable qualities. Include:
            - Animals with distinct personalities and traits
            - Natural behaviors woven into the story
            - Themes of cooperation in nature
            - Environmental awareness and respect for wildlife
            """,
            StoryCategory.EDUCATIONAL: """
            Weave learning naturally into the narrative. Include:
            - Educational content integrated seamlessly into the plot
            - Characters discovering new concepts through experience
            - Problem-solving that demonstrates learning principles
            - Curiosity and exploration as driving forces
            """,
            StoryCategory.MYSTERY: """
            Create gentle mysteries appropriate for young minds. Include:
            - Puzzles that can be solved through observation and logic
            - Clues that are discoverable and age-appropriate
            - Characters working together to solve problems
            - Satisfying revelations that make sense to children
            """,
            StoryCategory.FAMILY: """
            Explore family dynamics and relationships. Include:
            - Different family structures and traditions
            - Themes of love, support, and belonging
            - Generational wisdom and learning
            - Celebration of what makes families special
            """
        }
        return prompts.get(category, prompts[StoryCategory.ADVENTURE])
    
    def generate_story(self, story_request: StoryRequest, revision_notes: Optional[str] = None) -> Story:
        """Generate a bedtime story based on the request."""
        
        # Categorize if not already done
        if not story_request.category:
            story_request.category = self.categorize_request(story_request.request)
        
        category_guidance = self._get_category_specific_prompt(story_request.category)
        
        # Build the main storytelling prompt
        base_prompt = f"""You are a master storyteller specializing in bedtime stories for children aged 5-10.

STORY REQUEST: {story_request.request}

CATEGORY-SPECIFIC GUIDANCE:
{category_guidance}

STORY REQUIREMENTS:
- Length: {story_request.length_preference} (short: 200-400 words, medium: 400-800 words, long: 800-1200 words)
- Age-appropriate language and themes for ages 5-10
- Engaging narrative with a clear beginning, middle, and end
- Positive, comforting resolution suitable for bedtime
- Include a gentle moral or lesson naturally woven into the story
- Use vivid but not overstimulating imagery
- Create relatable characters children can connect with

STORY STRUCTURE:
1. Engaging opening that sets the scene
2. Character introduction with clear motivations
3. Conflict or challenge that drives the plot
4. Character growth and problem-solving
5. Satisfying, peaceful resolution
6. Subtle moral lesson or positive message

TONE AND STYLE:
- Warm, nurturing, and comforting
- Use simple but rich vocabulary
- Include dialogue to bring characters to life
- Create a sense of wonder and imagination
- End on a calm, reassuring note perfect for bedtime"""

        if revision_notes:
            base_prompt += f"\n\nREVISION NOTES: {revision_notes}\nPlease incorporate these suggestions while maintaining the story's core appeal."

        story_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=base_prompt),
            HumanMessage(content="Please write the bedtime story now. Start with a creative title, then tell the complete story.")
        ])
        
        result = self.llm.invoke(story_prompt.format_messages())
        story_content = result.content
        
        # Extract title and content
        lines = story_content.strip().split('\n')
        title = lines[0].strip()
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1]
        elif title.startswith('Title:'):
            title = title[6:].strip()
        
        # Find where the actual story begins
        story_start_idx = 1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() and not line.startswith('Title:'):
                story_start_idx = i
                break
        
        content = '\n'.join(lines[story_start_idx:]).strip()
        
        # Extract characters (simple heuristic)
        characters = self._extract_characters(content)
        
        # Generate moral lesson
        moral = self._extract_moral_lesson(content, story_request.category)
        
        return Story(
            title=title,
            content=content,
            category=story_request.category,
            age_appropriate=True,  # Will be verified by judge
            moral_lesson=moral,
            characters=characters
        )
    
    def _extract_characters(self, story_content: str) -> list[str]:
        """Extract main characters from the story using a simple LLM call."""
        character_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="Extract the main character names from this story. Return only the names, separated by commas. If no specific names are given, describe the characters (e.g., 'little girl', 'wise owl')."),
            HumanMessage(content=story_content[:1000])  # Limit for efficiency
        ])
        
        result = self.llm.invoke(character_prompt.format_messages())
        characters = [char.strip() for char in result.content.split(',')]
        return [char for char in characters if char]  # Filter empty strings
    
    def _extract_moral_lesson(self, story_content: str, category: StoryCategory) -> str:
        """Extract the moral lesson from the story."""
        moral_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="What is the main moral lesson or positive message in this bedtime story? Respond with a single sentence that captures the key takeaway for children."),
            HumanMessage(content=story_content[:1000])  # Limit for efficiency
        ])
        
        result = self.llm.invoke(moral_prompt.format_messages())
        return result.content.strip()
    
    def revise_story(self, original_story: Story, feedback: str) -> Story:
        """Revise a story based on feedback."""
        
        # Create revision prompt that handles various modification types
        revision_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are revising a bedtime story based on user feedback. 

ORIGINAL STORY:
Title: {original_story.title}
Category: {original_story.category}
Content: {original_story.content}

USER FEEDBACK: {feedback}

REVISION INSTRUCTIONS:
- If user wants it longer: Expand the story with more details, dialogue, character development, or additional scenes
- If user wants it shorter: Condense while keeping the core message and key plot points
- If user wants content changes: Modify characters, plot elements, setting, or themes as requested
- If user wants tone changes: Adjust the mood, excitement level, or emotional tone
- Maintain age-appropriateness for 5-10 year olds
- Keep the story's core charm and bedtime suitability
- Preserve the moral lesson unless specifically asked to change it

Please provide the complete revised story with a title."""),
            HumanMessage(content="Revise the story based on the feedback provided.")
        ])
        
        result = self.llm.invoke(revision_prompt.format_messages())
        story_content = result.content
        
        # Extract title and content
        lines = story_content.strip().split('\n')
        title = lines[0].strip()
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1]
        elif title.startswith('Title:'):
            title = title[6:].strip()
        
        # Find where the actual story begins
        story_start_idx = 1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() and not line.startswith('Title:'):
                story_start_idx = i
                break
        
        content = '\n'.join(lines[story_start_idx:]).strip()
        
        # Extract characters and moral lesson
        characters = self._extract_characters(content)
        moral = self._extract_moral_lesson(content, original_story.category)
        
        return Story(
            title=title,
            content=content,
            category=original_story.category,  # Keep original category
            age_appropriate=True,  # Will be verified by judge
            moral_lesson=moral,
            characters=characters
        )
