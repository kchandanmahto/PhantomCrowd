import json
import re


def _fix_json_string(text: str) -> str:
    """Fix common JSON issues from LLM responses."""
    # Replace backtick quotes with double quotes
    text = text.replace('`', '"')
    # Fix nested double quotes in string values: ""text"" -> \"text\"
    # Pattern: after ": " find ""...""  and fix them
    text = re.sub(r'""([^"]+)""', r'"\1"', text)
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    # Fix unescaped quotes inside string values by trying json.loads with increasingly aggressive fixes
    return text


def _aggressive_fix(text: str) -> str:
    """More aggressive JSON fixing for stubborn LLM outputs."""
    # Extract key-value pairs manually
    result = {}
    patterns = {
        "sentiment": r'"sentiment"\s*:\s*"(\w+)"',
        "sentiment_score": r'"sentiment_score"\s*:\s*([-\d.]+)',
        "engagement": r'"engagement"\s*:\s*"(\w+)"',
        "reasoning": r'"reasoning"\s*:\s*"([^"]*(?:"[^"]*)*)"',
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            val = m.group(1)
            if key == "sentiment_score":
                result[key] = float(val)
            else:
                result[key] = val

    # Extract comment (most problematic field)
    m = re.search(r'"comment"\s*:\s*"(.*?)"(?:\s*,|\s*})', text, re.DOTALL)
    if m:
        result["comment"] = m.group(1).replace('"', "'").replace('\n', ' ')
    elif "comment" not in result:
        # Fallback: grab text between "comment": and next key
        m = re.search(r'"comment"\s*:\s*"?(.*?)(?:"\s*,\s*"(?:engagement|reasoning))', text, re.DOTALL)
        if m:
            result["comment"] = m.group(1).strip().strip('"').replace('"', "'").replace('\n', ' ')

    if len(result) >= 4:
        result.setdefault("comment", "No comment")
        result.setdefault("reasoning", "")
        return json.dumps(result)
    return text


def extract_json(text: str):
    """Extract JSON from LLM response that may contain markdown or extra text."""
    text = text.strip()

    # Remove markdown code blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try with fixes
    try:
        return json.loads(_fix_json_string(text))
    except json.JSONDecodeError:
        pass

    # Try to find JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            try:
                return json.loads(_fix_json_string(match.group()))
            except json.JSONDecodeError:
                pass

    # Try to find JSON object
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            try:
                return json.loads(_fix_json_string(match.group()))
            except json.JSONDecodeError:
                pass

    # Last resort: find the largest {...} block
    matches = list(re.finditer(r"\{", text))
    for m in matches:
        start = m.start()
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        try:
                            return json.loads(_fix_json_string(candidate))
                        except json.JSONDecodeError:
                            break

    # Nuclear option: regex-extract individual fields
    try:
        fixed = _aggressive_fix(text)
        return json.loads(fixed)
    except (json.JSONDecodeError, ValueError):
        pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")
