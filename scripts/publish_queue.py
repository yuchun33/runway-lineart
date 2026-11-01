"""Publish the first unpublished queue item with completed lineart."""

import argparse
import json
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lineart.common import ROOT
from scripts.publish.instagram_client import publish, prepare_images
from scripts.run_queue import now, save
from scripts.publish.compose_post import source_info

QUEUE = ROOT / "scripts/queue.json"


def content(job):
    generations = [
        g
        for g in job["generations"]
        if g.get("status") == "completed" and g.get("post_status") == "completed"
    ]
    paths = []
    for relative in [g["post_path"] for g in generations]:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            raise ValueError(f"Invalid publishing image: {relative}")
        paths.append(path)
    if not generations or len(paths) > 10:
        raise ValueError("Publishing requires 1-10 composed cards.")
    caption = (
        f"{job['brand']} | {job['season']} | Look {job['look']}\n"
        + "Lineart: "
        + ", ".join(g["model"] for g in generations)
    )
    source = source_info(job, ROOT)
    if source.get("collection_url"):
        caption += "\nSource: " + source["collection_url"]
    if len(caption) > 2200:
        raise ValueError("Caption exceeds 2200 characters.")
    with TemporaryDirectory() as temporary:
        prepare_images(paths, Path(temporary))
    return paths, caption


def process(dry_run=False, prepare=False, send_prepared=False):
    raw = QUEUE.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    jobs = data["queue"]
    pending = [
        j for j in jobs if j.get("publish_status") in {"publishing", "needs_review"}
    ]
    if pending and not send_prepared:
        raise RuntimeError(
            "A previous publishing attempt needs review before continuing."
        )
    if send_prepared:
        if not pending:
            logging.info("No prepared post.")
            return 0
        if len(pending) != 1 or pending[0].get("publish_status") != "publishing":
            raise RuntimeError("Publishing state needs manual review.")
        job = pending[0]
    else:
        job = next(
            (
                j
                for j in jobs
                if j.get("published_at") is None
                and j.get("publish_status") in {None, "queued"}
                and any(
                    g.get("status") == "completed"
                    and g.get("post_status") == "completed"
                    and (ROOT / g["post_path"]).is_file()
                    for g in j.get("generations", [])
                )
            ),
            None,
        )
    if job is None:
        logging.info("No unpublished lineart ready.")
        return 0
    paths, caption = content(job)

    def update():
        nonlocal raw
        if QUEUE.read_text(encoding="utf-8-sig") != raw:
            raise RuntimeError(
                "queue.json changed during publishing; refusing to overwrite it."
            )
        save(QUEUE, data)
        raw = QUEUE.read_text(encoding="utf-8-sig")

    if dry_run:
        logging.info("Next post: %s; images: %s", caption, paths)
        return 0
    if not send_prepared:
        job.update(publish_status="publishing", publish_started_at=now())
        update()
    if prepare:
        return 0
    try:
        media = publish(paths, caption)
        job.update(
            published_at=now(),
            publish_status="published",
            instagram_media_id=str(media.pk),
            instagram_url=f"https://www.instagram.com/p/{media.code}/",
        )
        update()
    except Exception as exc:
        job.update(publish_status="needs_review", publish_error=type(exc).__name__)
        update()
        raise RuntimeError(
            "Publishing failed; check Instagram before resetting publish_status."
        ) from None
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument(
        "--prepare",
        action="store_true",
        help="Validate and save publishing state without posting",
    )
    mode.add_argument(
        "--send-prepared",
        action="store_true",
        help="Send the state just prepared by this workflow; never use for retries",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return process(**vars(args))
    except Exception as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
