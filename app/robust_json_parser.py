"""
Custom JSON output parser with error recovery for LLM outputs
Handles common formatting issues in LLM-generated JSON
"""
import json
import re
from typing import Any, Dict
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException


class RobustJsonOutputParser(JsonOutputParser):
    """
    Enhanced JSON parser that handles common LLM formatting issues:
    - Markdown code blocks (```json ... ```)
    - Unicode characters that should be escaped
    - Missing key names in JSON objects
    - Trailing commas
    """
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON output from LLM with error recovery.
        
        Args:
            text: Raw text output from LLM
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            OutputParserException: If JSON cannot be parsed after all recovery attempts
        """
        original_text = text
        
        try:
            # Step 1: Extract JSON from markdown code blocks
            text = self._extract_json_from_markdown(text)
            
            # Step 2: Attempt direct parsing
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
            
            # Step 3: Fix common formatting issues
            text = self._fix_unicode_issues(text)
            text = self._fix_malformed_objects(text)
            text = self._fix_trailing_commas(text)
            
            # Step 4: Try parsing again
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                # If still failing, try more aggressive fixes
                text = self._fix_unmatched_quotes(text)
                return json.loads(text)
                
        except json.JSONDecodeError as e:
            raise OutputParserException(
                f"Invalid json output: {original_text}\n\n"
                f"Error: {str(e)} at line {e.lineno}, column {e.colno}",
                llm_output=original_text
            ) from e
    
    @staticmethod
    def _extract_json_from_markdown(text: str) -> str:
        """Extract JSON from markdown code blocks"""
        # Look for ```json ... ``` or just ``` ... ```
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        return text
    
    @staticmethod
    def _fix_unicode_issues(text: str) -> str:
        """Fix common Unicode character issues"""
        # Replace Unicode hyphen (U+2011) with regular hyphen
        text = text.replace('‑', '-')
        # Replace other problematic Unicode characters
        text = text.replace('"', '"')  # Right double quotation mark
        text = text.replace('"', '"')  # Left double quotation mark
        text = text.replace(''', "'")  # Right single quotation mark
        text = text.replace(''', "'")  # Left single quotation mark
        return text
    
    @staticmethod
    def _fix_malformed_objects(text: str) -> str:
        """
        Fix multiple types of malformed JSON structures:
        1. Orphaned values with doubled quotes without key names: \"\"\"...\"\"\"
        2. Orphaned values with escaped leading quotes without key names: \\"...\\"
        3. Unescaped quotes within string values
        """
        lines = text.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Issue 1: Check if this line is a doubled-quoted string without a key
            if stripped.startswith('""') and stripped.endswith('""'):
                # Make sure the previous line ends with "action" to be safe
                if i > 0 and '"action"' in lines[i-1]:
                    # Extract content between the doubled quotes
                    content = stripped[2:-2]
                    # Reconstruct with proper key and single quotes
                    indent = line[:len(line) - len(stripped)]
                    fixed_line = f'{indent}"example": "{content}"'
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            # Issue 2: Check for escaped quote strings without key name
            elif stripped.startswith('\\"') and stripped.endswith('\\"') and ':"' not in stripped:
                # This is an orphaned value like: "\\"Developed...\\"
                if i > 0 and '"action"' in lines[i-1]:
                    # Unescape and wrap properly
                    content = stripped[2:-2]  # Remove leading \\" and trailing \\"
                    indent = line[:len(line) - len(stripped)]
                    fixed_line = f'{indent}"example": "{content}"'
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            # Issue 3: Fix unescaped quotes within "action" values
            elif '"action":' in stripped and stripped.endswith('",'):
                # Pattern: "action": "...content..." where content has unescaped quotes
                # Only fix if there are quotes that aren't already escaped
                pattern = r'^(\s*"action":\s*")(.*?)(", *$)'
                m = re.match(pattern, line)
                if m and '"' in m.group(2):
                    value = m.group(2)
                    # Only escape quotes that aren't already escaped
                    escaped_value = ""
                    for j, char in enumerate(value):
                        if char == '"' and (j== 0 or value[j-1] != '\\'):
                            # This quote is unescaped, escape it
                            escaped_value += '\\"'
                        else:
                            escaped_value += char
                    fixed_line = m.group(1) + escaped_value + m.group(3)
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_trailing_commas(text: str) -> str:
        """Remove trailing commas before closing brackets/braces"""
        # Remove trailing commas before ]
        text = re.sub(r',(\s*\])', r'\1', text)
        # Remove trailing commas before }
        text = re.sub(r',(\s*\})', r'\1', text)
        return text
    
    @staticmethod
    def _fix_unmatched_quotes(text: str) -> str:
        """Attempt to fix unmatched or doubled quotes"""
        # Replace doubled quotes ("") with single escaped quote (\")
        text = re.sub(r'""', r'\\"', text)
        return text
