"""
Hippocratic AI Bedtime Story Generator

"""

import os
import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

from models import ConversationState, StoryRequest
from story_workflow import StoryWorkflow, FeedbackProcessor


class BedtimeStoryChatInterface:
    """Professional terminal-based chat interface for bedtime story generation."""
    
    def __init__(self):
        self.console = Console()
        
        # Check for API key before initializing components
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        
        self.workflow = StoryWorkflow()
        self.feedback_processor = FeedbackProcessor()
        self.conversation_state = ConversationState()
        
    def display_welcome(self):
        """Display welcome message and instructions."""
        welcome_text = """
# 🌙 Bedtime Story Generator

Welcome to your personal bedtime storyteller! I create magical, age-appropriate stories just for you.

**How it works:**
- Tell me what kind of story you'd like to hear
- I'll create a wonderful bedtime story with the help of my story judge
- You can ask for changes or tell me what you think
- Type 'new story' to start fresh or 'quit' to exit

**Example requests:**
- "A story about a brave little mouse who goes on an adventure"
- "Tell me about a friendship between a girl and a magical tree"
- "I want a story with animals that teaches about kindness"
        """
        
        self.console.print(Panel(
            Markdown(welcome_text),
            title="🌙 Welcome",
            border_style="blue",
            padding=(1, 2)
        ))
    
    def get_story_preferences(self) -> str:
        """Get user preferences for story generation."""
        self.console.print("\n[bold blue]Let's customize your story![/bold blue]")
        
        # Length preference only
        length = Prompt.ask(
            "How long should the story be?",
            choices=["short", "medium", "long"],
            default="medium"
        )
        
        return length
    
    def display_story(self, story):
        """Display a story in a beautiful format."""
        # Title
        title_text = Text(story.title, style="bold magenta")
        self.console.print(Panel(
            title_text,
            title="📖 Your Story",
            border_style="magenta",
            padding=(0, 2)
        ))
        
        # Story content with nice formatting
        story_lines = story.content.split('\n')
        formatted_story = []
        
        for line in story_lines:
            line = line.strip()
            if line:
                # Add some visual spacing for paragraphs
                formatted_story.append(line)
                formatted_story.append("")
        
        story_text = '\n'.join(formatted_story)
        self.console.print(Panel(
            story_text,
            border_style="cyan",
            padding=(1, 2)
        ))
        
        # Story details
        details = f"**Category:** {story.category.value.title()}"
        if story.moral_lesson:
            details += f"\n**Lesson:** {story.moral_lesson}"
        if story.characters:
            details += f"\n**Characters:** {', '.join(story.characters)}"
        
        self.console.print(Panel(
            Markdown(details),
            title="✨ Story Details",
            border_style="green",
            padding=(0, 1)
        ))
    
    def get_user_feedback(self) -> Optional[str]:
        """Get user feedback on the story."""
        self.console.print("\n[bold yellow]What would you like to do next?[/bold yellow]")
        self.console.print("[dim]You can modify the story (make it longer/shorter, change characters, etc.), chat about it, or request a new story.[/dim]")
        
        feedback = Prompt.ask(
            "Your response",
            default="",
            show_default=False
        ).strip()
        
        if not feedback:
            return None
        
        # Check for special commands
        if feedback.lower() in ['quit', 'exit', 'bye']:
            return 'quit'
        elif feedback.lower() in ['new story', 'new', 'start over', 'different story']:
            return 'new_story'
        
        return feedback
    
    def display_chat_response(self, response: str):
        """Display a general chat response."""
        self.console.print(Panel(
            response,
            title="💬 Chat Response",
            border_style="blue",
            padding=(1, 2)
        ))
    
    def display_modification_summary(self, modification_eval: dict):
        """Display summary of story modification."""
        if modification_eval.get("feedback_addressed", True):
            status = "✅ Successfully Modified"
            color = "green"
        else:
            status = "⚠️ Partially Modified"
            color = "yellow"
        
        summary_text = f"**Status:** {modification_eval.get('evaluation_summary', 'Story was revised')}\n"
        
        if modification_eval.get("changes_made"):
            changes = modification_eval["changes_made"][:3]  # Show max 3 changes
            summary_text += f"**Changes Made:** {', '.join(changes)}"
        
        self.console.print(Panel(
            Markdown(summary_text),
            title=status,
            border_style=color,
            padding=(0, 1)
        ))
    
    def process_command(self, command: str) -> bool:
        """Process special commands. Returns True if command was handled."""
        command = command.lower().strip()
        
        if command in ['quit', 'exit', 'bye']:
            self.console.print(Panel(
                "Sweet dreams! Thanks for using the Bedtime Story Generator! 🌙✨",
                title="Goodbye",
                border_style="yellow"
            ))
            return True
        
        elif command in ['new story', 'new', 'start over', 'different story']:
            self.conversation_state = ConversationState()  # Reset state
            self.console.print("\n[bold green]Let's create a new story![/bold green]")
            return False  # Continue to new story creation
        
        elif command in ['help', '?']:
            self.display_help()
            return False
        
        return False
    
    def display_help(self):
        """Display help information."""
        help_text = """
**Available Commands:**
- `new story` or `new` - Start creating a new story
- `quit` or `exit` - Exit the program
- `help` or `?` - Show this help message

**Story Modifications:**
- "Make it longer/shorter" - Adjust story length
- "Add more animals" - Content modifications
- "Make it less scary" - Tone adjustments
- "Change the ending" - Specific revisions
- "Add more dialogue" - Style changes

**General Chat:**
- Ask questions about the story
- Have casual conversations
- Get writing tips or story advice
        """
        
        self.console.print(Panel(
            Markdown(help_text),
            title="Help",
            border_style="blue"
        ))
    
    def run_chat_session(self):
        """Run a single chat session for story generation."""
        # Get story request
        story_request = Prompt.ask(
            "\n[bold cyan]What kind of story would you like to hear?[/bold cyan]",
            default=""
        ).strip()
        
        if not story_request:
            return
        
        # Check for commands
        if self.process_command(story_request):
            return
        
        # Get preferences
        length = self.get_story_preferences()
        
        # Generate story
        self.console.print("\n[bold blue]✨ Creating your magical story...[/bold blue]")
        
        try:
            story = self.workflow.generate_story(
                request=story_request,
                length_preference=length
            )
            
            # Display the story
            self.display_story(story)
            
            # Update conversation state
            self.conversation_state.current_story = story
            
            # Get feedback and handle revisions
            while True:
                feedback = self.get_user_feedback()
                
                if not feedback:
                    break
                
                if feedback == 'quit':
                    return
                elif feedback == 'new_story':
                    break
                
                # Process feedback
                try:
                    revised_story, chat_response, feedback_type = self.workflow.process_user_feedback(
                        story, feedback, self.conversation_state
                    )
                    
                    if feedback_type == "general_chat":
                        # Display chat response
                        self.display_chat_response(chat_response)
                    
                    else:  # story_modification
                        self.console.print("\n[bold blue]✨ Modifying your story...[/bold blue]")
                        
                        # Get the modification evaluation from the judge
                        original_story = self.conversation_state.story_history[-1] if self.conversation_state.story_history else story
                        modification_eval = self.workflow.judge.evaluate_modification(original_story, revised_story, feedback)
                        
                        # Display modification summary
                        self.display_modification_summary(modification_eval)
                        
                        # Display revised story
                        self.console.print("\n[bold green]Here's your modified story:[/bold green]")
                        self.display_story(revised_story)
                        
                        # Update current story
                        story = revised_story
                        self.conversation_state.current_story = story
                    
                except Exception as e:
                    self.console.print(f"[bold red]Sorry, I had trouble processing your request: {str(e)}[/bold red]")
                    self.console.print("[dim]Please try rephrasing your request.[/dim]")
        
        except Exception as e:
            self.console.print(f"[bold red]Sorry, I encountered an error creating your story: {str(e)}[/bold red]")
            self.console.print("[dim]Please make sure your OpenAI API key is set correctly.[/dim]")
    
    def run(self):
        """Run the main chat interface."""
        # Check for API key
        if not os.getenv("OPENAI_API_KEY"):
            self.console.print(Panel(
                "[bold red]Error: OpenAI API key not found![/bold red]\n\n"
                "Please set your OpenAI API key as an environment variable:\n"
                "[bold]export OPENAI_API_KEY='your-api-key-here'[/bold]",
                title="Configuration Error",
                border_style="red"
            ))
            return
        
        # Display welcome
        self.display_welcome()
        
        # Main chat loop
        while True:
            try:
                self.run_chat_session()
                
                # Ask if user wants to continue
                if not Confirm.ask("\n[bold cyan]Would you like to create another story?[/bold cyan]"):
                    break
                    
            except KeyboardInterrupt:
                self.console.print("\n\n[bold yellow]Goodbye! Sweet dreams! 🌙[/bold yellow]")
                break
            except Exception as e:
                self.console.print(f"\n[bold red]An unexpected error occurred: {str(e)}[/bold red]")
                if not Confirm.ask("Would you like to try again?"):
                    break


def main():
    """Main entry point for the bedtime story generator."""
    try:
        chat_interface = BedtimeStoryChatInterface()
        chat_interface.run()
    except ValueError as e:
        console = Console()
        console.print(Panel(
            f"[bold red]Configuration Error![/bold red]\n\n{str(e)}\n\n"
            "Please set your OpenAI API key as an environment variable:\n"
            "[bold]export OPENAI_API_KEY='your-api-key-here'[/bold]",
            title="❌ Setup Required",
            border_style="red"
        ))
    except Exception as e:
        console = Console()
        console.print(f"[bold red]Unexpected error: {str(e)}[/bold red]")


if __name__ == "__main__":
    main()