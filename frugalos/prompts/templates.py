"""
Prompt template definitions for frugalos.

This module contains versioned prompt templates with schema-aware construction,
few-shot example support, and task-specific instructions.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
import json

class PromptTemplate:
    """Base class for prompt templates."""

    def __init__(self, version: str, template_dict: Dict[str, Any]):
        self.version = version
        self.template_dict = template_dict

    def build_prompt(
        self,
        goal: str,
        context: str,
        schema: Optional[Dict] = None,
        examples: Optional[List[Dict]] = None
    ) -> str:
        """Build a complete prompt from template and inputs."""
        template = self.template_dict

        # Build system instructions
        system_prompt = template["system"] + "\n\n"

        # Add schema instructions if schema provided
        schema_section = ""
        if schema:
            schema_section = template["schema_instruction"].format(
                schema=json.dumps(schema, indent=2)
            ) + "\n\n"

        # Add examples if provided
        examples_section = ""
        if examples:
            examples_section = template["examples_instruction"] + "\n"
            for i, example in enumerate(examples[:template.get("max_examples", 3)]):
                examples_section += f"\nExample {i+1}:\n"
                examples_section += f"Input: {example['input']}\n"
                examples_section += f"Output: {example['output']}\n"
            examples_section += "\n"

        # Add output format instructions
        output_section = template["output_format"] + "\n\n"

        # Add task context
        task_section = f"Task: {goal}\n\n"

        # Add context
        context_section = "Context (may be empty):\n"
        context_section += "---\n"
        context_section += context[:template.get("context_max_chars", 4000)]
        context_section += "\n---\n\n"

        # Final instruction
        final_instruction = template["final_instruction"]

        return (
            system_prompt +
            schema_section +
            examples_section +
            output_section +
            task_section +
            context_section +
            final_instruction
        )

# Initial template (v1.0) - Schema-aware with clear instructions
TEMPLATE_V1_0 = {
    "version": "1.0",
    "system": "You are a careful assistant specializing in structured data extraction and task completion.",
    "schema_instruction": "You MUST produce valid JSON that matches this exact schema:\n{schema}\nYour output must conform to all required fields, types, and constraints.",
    "examples_instruction": "Follow these examples of the expected input-output format:",
    "output_format": "Return ONLY valid JSON. Do not include explanations, markdown formatting, or any extra text outside the JSON structure.",
    "final_instruction": "Return ONLY the JSON output (no extra prose):",
    "context_max_chars": 4000,
    "max_examples": 3
}

# General-purpose template for data extraction tasks
TEMPLATE_EXTRACTION_V1_0 = {
    "version": "extraction-1.0",
    "system": "You are a careful data extraction assistant. Your job is to accurately extract structured information from unstructured text or documents.",
    "schema_instruction": "Extract information to match this JSON schema exactly:\n{schema}\nAll required fields must be present and data types must match.",
    "examples_instruction": "Examples of successful extractions:",
    "output_format": "Return ONLY valid JSON. Do not include explanations, markdown, or extra text. Focus on accuracy and completeness.",
    "final_instruction": "Extract the requested information and return it as valid JSON:",
    "context_max_chars": 4000,
    "max_examples": 3
}

# Template for transformation tasks (format conversion, data reshaping)
TEMPLATE_TRANSFORMATION_V1_0 = {
    "version": "transformation-1.0",
    "system": "You are a data transformation assistant. Your job is to convert data from one format to another while preserving all information accurately.",
    "schema_instruction": "Transform the input data to match this JSON schema:\n{schema}\nMaintain data integrity and ensure all information is properly mapped.",
    "examples_instruction": "Examples of successful transformations:",
    "output_format": "Return ONLY valid JSON. Do not include explanations or notes about the transformation process.",
    "final_instruction": "Transform the data according to the requirements and return the result as valid JSON:",
    "context_max_chars": 4000,
    "max_examples": 2
}

# Template for analysis tasks (summarization, insights, reasoning)
TEMPLATE_ANALYSIS_V1_0 = {
    "version": "analysis-1.0",
    "system": "You are an analytical assistant. Your job is to analyze information and provide structured insights, summaries, or reasoned conclusions.",
    "schema_instruction": "Structure your analysis to match this JSON schema:\n{schema}\nProvide clear, well-reasoned analysis in the specified format.",
    "examples_instruction": "Examples of successful analyses:",
    "output_format": "Return ONLY valid JSON. Include your analysis in the structured format without additional commentary.",
    "final_instruction": "Analyze the information and provide your structured insights as valid JSON:",
    "context_max_chars": 4000,
    "max_examples": 2
}

# Template for code-related tasks
TEMPLATE_CODE_V1_0 = {
    "version": "code-1.0",
    "system": "You are a code generation and analysis assistant. Your job is to write, debug, or refactor code according to specific requirements.",
    "schema_instruction": "Generate or analyze code to match this JSON schema:\n{schema}\nEnsure code correctness, proper formatting, and adherence to best practices.",
    "examples_instruction": "Examples of successful code tasks:",
    "output_format": "Return ONLY valid JSON. Include code in the specified JSON fields without extra explanation unless requested.",
    "final_instruction": "Complete the code task and return the result as valid JSON:",
    "context_max_chars": 4000,
    "max_examples": 2
}

# Default template registry
TEMPLATE_REGISTRY = {
    "1.0": TEMPLATE_V1_0,
    "extraction-1.0": TEMPLATE_EXTRACTION_V1_0,
    "transformation-1.0": TEMPLATE_TRANSFORMATION_V1_0,
    "analysis-1.0": TEMPLATE_ANALYSIS_V1_0,
    "code-1.0": TEMPLATE_CODE_V1_0,
}

# Default template selection based on task characteristics
DEFAULT_TEMPLATES = {
    "default": "1.0",
    "extraction": "extraction-1.0",
    "transformation": "transformation-1.0",
    "analysis": "analysis-1.0",
    "code": "code-1.0"
}

def get_template(template_key: str) -> PromptTemplate:
    """Get a prompt template by key."""
    template_dict = TEMPLATE_REGISTRY.get(template_key, TEMPLATE_REGISTRY["1.0"])
    return PromptTemplate(template_key, template_dict)

def list_templates() -> List[str]:
    """List all available template versions."""
    return list(TEMPLATE_REGISTRY.keys())

def get_default_template() -> str:
    """Get the default template key."""
    return "1.0"