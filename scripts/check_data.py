"""Validate queued paths and the static index without credentials or API calls."""

import json
from pathlib import Path

from scripts.lineart.common import ROOT
from scripts.update_web_data import build_data


def main():
    queue = json.loads((ROOT / "scripts/queue.json").read_text(encoding="utf-8"))[
        "queue"
    ]
    outputs = set()
    for job in queue:
        original = (ROOT / job["image_path"]).resolve()
        assert (
            original.is_relative_to(ROOT) and original.is_file()
        ), f"Invalid input: {original}"
        assert job["status"] in {
            "queued",
            "processing",
            "partial",
            "completed",
            "failed",
        }
        assert job["generations"], "Missing generations"
        for generation in job["generations"]:
            assert generation["provider"] in {"openai", "gemini"}
            assert generation["model"]
            assert generation["status"] in {
                "queued",
                "processing",
                "completed",
                "failed",
            }
            output = (ROOT / generation["output_path"]).resolve()
            assert (
                output.is_relative_to(ROOT)
                and output.suffix == ".png"
                and output != original
            )
            assert output not in outputs, f"Duplicate output: {output}"
            outputs.add(output)
            if generation["status"] == "completed":
                assert output.is_file(), f"Missing completed output: {output}"
    # Validate index structure, unique IDs and all referenced files. New unindexed
    # outputs are allowed here; update_web_data --check is the explicit sync check.
    data = json.loads((ROOT / "web/data.json").read_text(encoding="utf-8"))
    for brand in data["brands"]:
        ids = set()
        for look in brand["looks"]:
            assert look["id"] not in ids
            ids.add(look["id"])
            for image in [look["original"], *look["linearts"]]:
                file = (ROOT / "web" / image["src"]).resolve()
                assert (
                    file.is_relative_to(ROOT) and file.is_file()
                ), f"Broken website image: {file}"
    build_data()
    print("Queue and website paths verified.")


if __name__ == "__main__":
    main()
