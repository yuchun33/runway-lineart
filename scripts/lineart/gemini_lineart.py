"""Gemini image generation, adapted from the original main.py client setup."""

import mimetypes
import os
from pathlib import Path

from .common import ROOT, prompt

MODEL = 'gemini-3.1-flash-image'


def load_api_key():
    for env_file in (ROOT / 'scripts' / '.env', ROOT / '.env'):
        if env_file.exists():
            for line in env_file.read_text(encoding='utf-8-sig').splitlines():
                name, separator, value = line.strip().partition('=')
                if separator and name.strip() == 'GEMINI_API_KEY':
                    os.environ.setdefault(name.strip(), value.strip().strip('\"\''))
    return os.getenv('GEMINI_API_KEY')


def generate(original, destination, model=MODEL):
    api_key = load_api_key()
    if not api_key:
        raise ValueError('Missing GEMINI_API_KEY in environment, scripts/.env or project .env')
    try:
        from google import genai
        from google.genai import types

        with genai.Client(api_key=api_key, http_options=types.HttpOptions(
                timeout=600_000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
            response = client.models.generate_content(
                model=model,
                contents=[prompt, types.Part.from_bytes(
                    data=original.read_bytes(),
                    mime_type=mimetypes.guess_type(original.name)[0] or 'image/jpeg')],
                config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE']),
            )
        for part in response.parts or []:
            if part.inline_data and part.inline_data.mime_type == 'image/png':
                data = part.inline_data.data
                if not data or not data.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Gemini returned invalid PNG data')
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix('.png.part')
                temporary.write_bytes(data)
                temporary.replace(destination)
                return
        raise ValueError('Gemini returned no PNG image; output was not saved')
    except Exception as exc:
        raise RuntimeError(str(exc).replace(api_key, '[REDACTED]')) from None
