from openai import AsyncOpenAI

from app.core.config import settings
from app.services.json_utils import extract_json

PERSONA_GENERATION_PROMPT = """You are a demographic and psychographic persona generator.
Generate {count} diverse, realistic audience personas for evaluating the following content:

Content Type: {content_type}
Content: {content}

{audience_config}

Each persona must have:
- name: A realistic name
- age: Integer between 13-80
- gender: "male", "female", or "non-binary"
- occupation: Their job or role
- interests: List of 3-5 interests
- personality: Brief personality description (1 sentence)
- social_media_usage: "heavy", "moderate", or "light"

Ensure diversity in age, gender, occupation, and personality types.
Return ONLY a JSON array of persona objects, no other text."""


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


async def generate_personas(
    content: str,
    content_type: str,
    count: int,
    audience_config: dict | None = None,
) -> list[dict]:
    config_text = ""
    if audience_config:
        config_text = f"Audience targeting: {json.dumps(audience_config)}"

    client = _get_client()

    personas = []
    remaining = count

    while remaining > 0:
        batch = min(remaining, 20)
        response = await client.chat.completions.create(
            model=settings.llm_analysis_model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": PERSONA_GENERATION_PROMPT.format(
                        count=batch,
                        content_type=content_type,
                        content=content[:500],
                        audience_config=config_text,
                    ),
                }
            ],
        )

        text = response.choices[0].message.content
        batch_personas = extract_json(text)
        personas.extend(batch_personas)
        remaining -= batch

    return personas[:count]
