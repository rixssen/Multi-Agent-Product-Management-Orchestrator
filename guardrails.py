import re
from typing import Tuple

BANNED_INPUT_PATTERNS = [
    r"\b(exploit|malware|keylogger|backdoor|hack into|bypass authentication)\b",
    r"\b(drop table|select \* from users|union select)\b",  # Basic SQLi
    r"ignore previous instructions",  # Simple prompt injection
    r"system prompt:",
]

def validate_input_prompt(prompt: str) -> Tuple[bool, str]:
    """
    Checks if the user prompt is safe and valid.
    Returns: (is_safe, error_message)
    """
    if not prompt or not prompt.strip():
        return False, "Input prompt cannot be empty."
        
    if len(prompt.strip()) < 10:
        return False, "Input prompt is too short. Please describe your product idea in more detail."
        
    for pattern in BANNED_INPUT_PATTERNS:
        if re.search(pattern, prompt, re.IGNORECASE):
            return False, f"Input rejected: Prompt matched safety filter rule."
            
    return True, ""

def validate_output_content(content: str) -> Tuple[bool, str]:
    """
    Checks if the generated agent output is safe and formatted correctly.
    Returns: (is_safe, error_message)
    """
    if not content or not content.strip():
        return False, "Generated content is empty."
        
    # Check for unclosed markdown backticks
    backticks_count = content.count("```")
    if backticks_count % 2 != 0:
        return False, "Formatting error: Unclosed markdown code blocks detected."
        
    # Basic XSS check inside generated text
    if "<script" in content.lower():
        return False, "Security warning: HTML script tags detected in agent response."
        
    return True, ""
