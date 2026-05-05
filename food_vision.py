#!/usr/bin/env python3
"""Spike: identify food in an image for the Israeli kids' nutrition app."""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = """אתה מזהה אוכל באפליקציית תזונה לילדות בנות 9-12 בישראל.
המטרה: לזהות מנה, להעריך גודל, ולתת "צבע רמזור" וכוכבי אנרגיה — בלי להציג קלוריות לילדה.

עקרונות:
- זהה אוכל ישראלי טיפוסי: חומוס, פלאפל, פיתה, שניצל, סלט ישראלי, בורקס,
  שווארמה, אורז, פסטה, פירה, ירקות חיים, לחם, גבינות, יוגורט, פירות, חטיפי בוקר.
- הערך גודל מנה לפי התמונה (גרמים בערך). אם יש סימוכין לגודל (יד, צלחת, סכו"ם) — השתמש.
- צבע רמזור:
  • green:  ירקות, פירות, חלבון רזה, דגנים מלאים
  • yellow: פחמימות פשוטות, גבינות שמנות, מנות מעורבות
  • red:    מטוגן, ממותק, מעובד מאוד
- כוכבי אנרגיה (1-5): כמה הארוחה תיתן כוח איכותי לפעילות.
  5=הרבה אנרגיה איכותית, 1=ריקה/מעט.
- אם התמונה לא ברורה או אינה אוכל — is_food=false, confidence=low, והסבר ב-notes.

אל תזכיר קלוריות. אל תשפוט. זיהוי מקצועי ועובדתי בלבד."""

SCHEMA = {
    "type": "object",
    "properties": {
        "is_food": {"type": "boolean"},
        "dish_name_he": {"type": "string"},
        "dish_name_en": {"type": "string"},
        "ingredients": {
            "type": "array",
            "items": {"type": "string"},
        },
        "estimated_grams": {"type": "integer"},
        "traffic_light": {
            "type": "string",
            "enum": ["green", "yellow", "red"],
        },
        "energy_stars": {
            "type": "integer",
            "enum": [1, 2, 3, 4, 5],
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "notes": {"type": "string"},
    },
    "required": [
        "is_food",
        "dish_name_he",
        "dish_name_en",
        "ingredients",
        "estimated_grams",
        "traffic_light",
        "energy_stars",
        "confidence",
        "notes",
    ],
    "additionalProperties": False,
}

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def build_image_block(source: str) -> dict:
    if source.startswith(("http://", "https://")):
        return {"type": "image", "source": {"type": "url", "url": source}}

    path = Path(source)
    if not path.exists():
        sys.exit(f"file not found: {source}")

    media_type, _ = mimetypes.guess_type(path)
    if media_type not in SUPPORTED_IMAGE_TYPES:
        sys.exit(f"unsupported image type: {media_type or 'unknown'}")

    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def analyze(source: str) -> dict:
    client = anthropic.Anthropic()
    image_block = build_image_block(source)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": [
                    image_block,
                    {"type": "text", "text": "מה רואים בתמונה? תן ניתוח מלא לפי הסכמה."},
                ],
            }
        ],
    )

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Identify food in an image (Israeli kids' meals)."
    )
    parser.add_argument("image", help="Path to image file or http(s) URL")
    args = parser.parse_args()

    result = analyze(args.image)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
