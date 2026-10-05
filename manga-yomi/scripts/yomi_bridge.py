"""Prepare/review comic-translate exports. Python standard library only."""
import argparse
import json
import re
from pathlib import Path

def load(path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError(f"Duplicate JSON key: {k}")
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)

def raw_valid(raw):
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Raw input must be a nonempty object")
    if any(not re.fullmatch(r"block_[0-9]+", k) or not isinstance(v, str) for k, v in raw.items()):
        raise ValueError("Expected block_N keys with string values")

def export(raw, review, allow_draft=False):
    raw_valid(raw)
    if not isinstance(review, dict) or not isinstance(review.get("blocks"), list):
        raise ValueError("Review must contain a blocks list")
    found = {}
    pending = []
    for block in review["blocks"]:
        if not isinstance(block, dict):
            raise ValueError("Each block must be an object")
        key = block.get("id")
        if not isinstance(key, str) or key not in raw or key in found:
            raise ValueError(f"Unknown or duplicate block id: {key}")
        if block.get("source") != raw[key]:
            raise ValueError(f"Original source changed: {key}")
        value = block.get("translation")
        if not isinstance(value, str) or (raw[key].strip() and not value.strip()):
            raise ValueError(f"Missing or invalid translation: {key}")
        status = block.get("status")
        if status not in {"verified", "proposed", "needs_review"}:
            raise ValueError(f"Invalid review status: {key}")
        if status != "verified":
            pending.append(key)
        found[key] = value
    missing = set(raw) - set(found)
    if missing:
        raise ValueError(f"Missing blocks: {sorted(missing)}")
    if pending and not allow_draft:
        raise ValueError(f"Unconfirmed blocks: {pending}; review or use --allow-draft")
    return {k: found[k] for k in raw}, pending

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "export"):
        p = sub.add_parser(command)
        p.add_argument("--raw", required=True)
        p.add_argument("--out", required=True)
        if command == "prepare":
            p.add_argument("--page-id", default="p001")
        else:
            p.add_argument("--review", required=True)
            p.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    try:
        raw = load(args.raw)
        raw_valid(raw)
        if args.command == "prepare":
            data = {"page_id": args.page_id, "blocks": [{"id":k,"source":v,"corrected_source":v,"translation":"","status":"needs_review","speaker":None,"notes":[]} for k,v in raw.items()]}
        else:
            data, pending = export(raw, load(args.review), args.allow_draft)
            print(f"Structure checked; unconfirmed blocks: {len(pending)}. Semantic accuracy not checked.")
        out = Path(args.out)
        inputs = [Path(args.raw)] + ([Path(args.review)] if args.command == "export" else [])
        if out.resolve() in [p.resolve() for p in inputs]:
            raise ValueError("Output must not overwrite an input")
        if out.exists():
            raise ValueError("Output already exists; choose a new filename")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, f"Validation failed: {exc}\n")

if __name__ == "__main__":
    main()
