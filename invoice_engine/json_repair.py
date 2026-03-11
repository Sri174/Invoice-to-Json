"""
json_repair.py
--------------
Utility functions for repairing malformed JSON from LLM responses.
Handles common syntax errors from Gemini and other LLMs.
"""

import json
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_json_with_repair(json_str: str) -> Dict[str, Any]:
    """
    Parse JSON with automatic repair for common LLM errors.
    
    Tries multiple repair strategies in order:
    1. Direct parse
    2. Syntax error repair
    3. Extract valid JSON portion
    4. Aggressive structural repair
    
    Args:
        json_str: JSON string to parse (potentially malformed)
    
    Returns:
        Parsed dict
    
    Raises:
        ValueError: If all repair attempts fail
    """
    # Strategy 1: Try direct parse
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"Initial JSON parse failed: {str(e)}")
    
    # Strategy 2: Fix common syntax errors
    try:
        repaired = repair_json_syntax(json_str)
        result = json.loads(repaired)
        logger.info("JSON repaired successfully using syntax repair")
        return result
    except json.JSONDecodeError as e:
        logger.debug(f"Syntax repair parse failed: {str(e)}")
    
    # Strategy 3: Extract valid JSON portion
    try:
        extracted = extract_valid_json(json_str)
        result = json.loads(extracted)
        logger.info("JSON repaired successfully using extraction")
        return result
    except Exception as e:
        logger.debug(f"JSON extraction failed: {str(e)}")
    
    # Strategy 4: Aggressive repair
    try:
        fixed = aggressive_json_repair(json_str)
        result = json.loads(fixed)
        logger.info("JSON repaired successfully using aggressive repair")
        return result
    except Exception as e:
        logger.error(f"All JSON repair strategies failed: {str(e)}")
        raise ValueError(f"Could not parse or repair JSON: {str(e)}")


def repair_json_syntax(json_str: str) -> str:
    """
    Repair common JSON syntax errors from LLMs.
    
    Common errors fixed:
    - Missing closing braces in array items
    - Trailing commas
    - Malformed number formatting
    
    Args:
        json_str: Malformed JSON string
    
    Returns:
        Repaired JSON string
    """
    # Fix: Missing closing brace before comma in array items
    # Pattern: "amount": 94.14\n    , -> "amount": 94.14\n    },
    json_str = re.sub(
        r'(:\s*\d+\.?\d*)\s*\n\s*,\s*\n\s*({|")', 
        r'\1\n    },\n    \2', 
        json_str
    )
    
    # Fix: Missing closing brace with direct comma
    # Pattern: "amount": 94.14\n    , -> "amount": 94.14\n    },
    json_str = re.sub(
        r'(:\s*(?:\d+\.?\d*|"[^"]*"|null|true|false))\s*,\s*\n\s*"line_number"', 
        r'\1\n    },\n    {\n      "line_number"', 
        json_str
    )
    
    # Fix: Trailing commas before closing brackets/braces
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    # Fix: Missing comma between array items
    json_str = re.sub(r'}\s*\n\s*{', r'},\n    {', json_str)
    
    # Fix: Double commas
    json_str = re.sub(r',,+', r',', json_str)
    
    # Fix: Comma after closing bracket in arrays
    json_str = re.sub(r'\]\s*,\s*,', r'],', json_str)
    
    return json_str


def extract_valid_json(json_str: str) -> str:
    """
    Extract the largest valid JSON object from a string.
    Uses brace matching to find complete objects.
    
    Args:
        json_str: String potentially containing valid JSON
    
    Returns:
        Extracted JSON string
    
    Raises:
        ValueError: If no valid JSON object found
    """
    # Find the first opening brace
    start = json_str.find('{')
    if start == -1:
        raise ValueError("No JSON object found in string")
    
    # Track braces to find matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False
    
    for i in range(start, len(json_str)):
        char = json_str[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                
                if brace_count == 0:
                    # Found complete object
                    return json_str[start:i+1]
    
    # Could not find complete object
    raise ValueError("No complete JSON object found")


def aggressive_json_repair(json_str: str) -> str:
    """
    Aggressive JSON repair by rebuilding arrays.
    Specifically handles broken line_items arrays.
    
    Args:
        json_str: Broken JSON string
    
    Returns:
        Repaired JSON string
    """
    # Focus on line_items array - most common error location
    if '"line_items"' not in json_str:
        return json_str
    
    # Find the line_items array
    match = re.search(r'"line_items"\s*:\s*\[', json_str)
    if not match:
        return json_str
    
    start_pos = match.end()
    
    # Extract all complete line item objects
    items = extract_array_items(json_str, start_pos)
    
    if not items:
        return json_str
    
    # Rebuild the line_items array
    items_str = ',\n    '.join(items)
    before_array = json_str[:match.start()]
    
    # Find what comes after line_items
    after_match = re.search(r'\],\s*"', json_str[start_pos:])
    if after_match:
        after_pos = start_pos + after_match.start()
        after_array = json_str[after_pos+1:]
        
        # Reconstruct JSON with repaired array
        return f'{before_array}"line_items": [\n    {items_str}\n  ],{after_array}'
    
    return json_str


def extract_array_items(json_str: str, start_pos: int) -> list:
    """
    Extract complete objects from an array.
    
    Args:
        json_str: JSON string containing array
        start_pos: Position where array content starts (after '[')
    
    Returns:
        List of complete object strings
    """
    items = []
    current_item = ""
    brace_count = 0
    in_string = False
    escape_next = False
    
    for i in range(start_pos, len(json_str)):
        char = json_str[i]
        
        if escape_next:
            escape_next = False
            if brace_count > 0:
                current_item += char
            continue
        
        if char == '\\':
            escape_next = True
            if brace_count > 0:
                current_item += char
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            if brace_count > 0:
                current_item += char
            continue
        
        if not in_string:
            if char == '{':
                brace_count += 1
                current_item += char
            elif char == '}':
                brace_count -= 1
                current_item += char
                
                if brace_count == 0 and current_item.strip():
                    # Complete item found
                    items.append(current_item.strip())
                    current_item = ""
            elif char == ']':
                # End of array
                break
            elif brace_count > 0:
                current_item += char
    
    return items


def clean_json_string(text: str) -> str:
    """
    Clean common formatting issues in JSON strings.
    
    Args:
        text: Raw text potentially containing JSON
    
    Returns:
        Cleaned string
    """
    text = text.strip()
    
    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()
    
    # Remove any leading/trailing non-JSON characters
    start = text.find('{')
    if start > 0:
        text = text[start:]
    
    return text


def validate_json_structure(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    Validate that data matches schema structure.
    
    Args:
        data: Data dict to validate
        schema: Schema dict to validate against
    
    Returns:
        True if structure matches
    """
    for key in schema.keys():
        if key not in data:
            logger.warning(f"Missing key: {key}")
            return False
    
    return True
