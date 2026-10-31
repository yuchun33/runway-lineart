import base64
import os
from pathlib import Path

from .common import ROOT, prompt

MODEL = "gpt-image-2.5-sunburst"


def load_api_key():
    # An explicitly set environment variable takes precedence over either file.
    for env_file in (ROOT / "scripts" / ".env", ROOT / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                name, separator, value = line.strip().partition("=")
                if separator and name.strip() == "OPENAI_API_KEY":
                    os.environ.setdefault(name.strip(), value.strip().strip("\"'"))
    return os.getenv("OPENAI_API_KEY")


def generate(original, destination, model=MODEL):
    """Generate and save one PNG; API setup and secret handling stay in this module."""
    api_key = load_api_key()
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY. Set it in the environment, scripts/.env or project .env.")
    try:
        from openai import OpenAI

        # Do not retry uncertain paid requests automatically.
        with OpenAI(api_key=api_key, timeout=600, max_retries=0) as client:
            with original.open("rb") as image:
                response = client.images.edit(
                    model=model, image=[image], prompt=prompt, n=1, output_format="png",
                )
        if not response.data or not response.data[0].b64_json:
            raise ValueError("API returned no image")
        data = base64.b64decode(response.data[0].b64_json, validate=True)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("API output is not a PNG image")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".png.part")
        temporary.write_bytes(data)
        temporary.replace(destination)
    except Exception as exc:
        raise RuntimeError(str(exc).replace(api_key, "[REDACTED]")) from None
