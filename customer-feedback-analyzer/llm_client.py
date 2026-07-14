"""Thin wrapper around the OpenAI API: prompt in, text out.

Kept to a single function so every other module can depend on a plain
`str -> str` interface and swap in a mock for testing without touching
anything about how prompts are built or responses are parsed.
"""

import os

from openai import OpenAI

MODEL = "gpt-4o-mini"


def call_llm(prompt: str) -> str:
    """Send `prompt` to the OpenAI API and return the raw text response."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return response.choices[0].message.content
