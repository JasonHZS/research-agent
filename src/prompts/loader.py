"""
Prompt Loader Module

This module provides functionality to load and render Jinja2 templates
from markdown files for agent prompts.
"""

from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptLoader:
    """
    A loader for managing and rendering Jinja2 prompt templates.
    
    This class provides a convenient way to load markdown prompt templates
    and render them with dynamic variables.
    """
    
    _instance: Optional["PromptLoader"] = None
    _env: Optional[Environment] = None
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the PromptLoader.
        
        Args:
            templates_dir: Directory containing prompt templates.
                          Defaults to the 'templates' subdirectory.
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        
        self.templates_dir = templates_dir
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    @classmethod
    def get_instance(cls) -> "PromptLoader":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def load(self, template_name: str, **kwargs: Any) -> str:
        """
        Load and render a prompt template.
        
        Args:
            template_name: Name of the template file (with or without .md extension).
            **kwargs: Variables to pass to the template for rendering.
            
        Returns:
            Rendered prompt string.
            
        Raises:
            jinja2.TemplateNotFound: If the template file doesn't exist.
        """
        if not template_name.endswith(".md"):
            template_name = f"{template_name}.md"
        
        template = self._env.get_template(template_name)
        return template.render(**kwargs)
    
    def list_templates(self) -> list[str]:
        """
        List all available prompt templates.
        
        Returns:
            List of template file names.
        """
        return [
            f.name for f in self.templates_dir.glob("*.md")
            if f.is_file()
        ]


def load_prompt(template_name: str, **kwargs: Any) -> str:
    """
    Convenience function to load and render a prompt template.
    
    This uses the singleton PromptLoader instance.
    
    Args:
        template_name: Name of the template file (with or without .md extension).
        **kwargs: Variables to pass to the template for rendering.
        
    Returns:
        Rendered prompt string.
        
    Example:
        >>> prompt = load_prompt("research_agent", tools=["arxiv", "hacker_news"])
    """
    return PromptLoader.get_instance().load(template_name, **kwargs)
