"""
preview_video.py  —  Generate a pre-signed S3 URL to preview a video in browser

Usage:
  # Preview a specific clip
  python preview_video.py --date "2026-08-06" --start "01:01:01" --end "01:02:00"

  # List all clips for a date and pick one
  python preview_video.py --date "2026-08-06" --list

  # Preview latest uploaded clip
  python preview_video.py --latest
"""

import argparse
import os
import webbrowser
from datetime import datetime

import boto3

S3_BUCKET   = os.getenv("S3_BUCKET",   "gtrac")
S3_REGION   = os.getenv("S3_REGION",   "us-east-1")
S3_PREFIX = os.getenv("S3_PREFIX", "videos")
IMEI      = os.getenv("DEVICE_IMEI", "670078167679")
EXPIRES   = 3600  # URL valid for 1 hour


def s3():
    return boto3.client("s3", region_name=S3_REGION)


def build_key(date_str: str, start: str, end: str) -> str:
    return (
        f"{S3_PREFIX}/{IMEI}/{date_str}/"
        f"clip_{start.replace(':', '')}-{end.replace(':', '')}.mp4"
    )


def generate_url(key: str) -> str:
    return s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=EXPIRES,
    )


def list_clips(date_str: str) -> list[str]:
    prefix   = f"{S3_PREFIX}/{IMEI}/{date_str}/"
    response = s3().list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    contents = response.get("Contents", [])
    return sorted(obj["Key"] for obj in contents if obj["Key"].endswith(".mp4"))


def latest_clip() -> str | None:
    response = s3().list_objects_v2(Bucket=S3_BUCKET, Prefix=f"{S3_PREFIX}/{IMEI}/")
    contents = response.get("Contents", [])
    mp4s     = [o for o in contents if o["Key"].endswith(".mp4")]
    if not mp4s:
        return None
    return sorted(mp4s, key=lambda o: o["LastModified"])[-1]["Key"]


def print_url(key: str):
    url = generate_url(key)
    print(f"\n  Clip  : {key}")
    print(f"  URL   : {url}")
    print(f"\n  → Opening in browser... (link valid for {EXPIRES//60} minutes)\n")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Preview Track360 S3 video clip")
    parser.add_argument("--date",   help="YYYY-MM-DD")
    parser.add_argument("--start",  help="HH:MM:SS  start time of the clip")
    parser.add_argument("--end",    help="HH:MM:SS  end time of the clip")
    parser.add_argument("--list",   action="store_true", help="List all clips for --date and pick one")
    parser.add_argument("--latest", action="store_true", help="Preview the most recently uploaded clip")
    args = parser.parse_args()

    # ── Latest clip ───────────────────────────────────────────────────────────
    if args.latest:
        key = latest_clip()
        if not key:
            print("No clips found in S3.")
            return
        print_url(key)
        return

    # ── List clips for a date ─────────────────────────────────────────────────
    if args.list:
        if not args.date:
            print("ERROR: --list requires --date YYYY-MM-DD")
            return
        clips = list_clips(args.date)
        if not clips:
            print(f"No clips found for {args.date}")
            return
        print(f"\n  Clips for {args.date}:")
        for i, key in enumerate(clips, 1):
            fname = key.split("/")[-1]
            print(f"  [{i:3}] {fname}")
        print()
        choice = input("  Enter number to preview (or press Enter to exit): ").strip()
        if not choice:
            return
        key = clips[int(choice) - 1]
        print_url(key)
        return

    # ── Specific clip ─────────────────────────────────────────────────────────
    if args.date and args.start and args.end:
        key = build_key(args.date, args.start, args.end)
        print_url(key)
        return

    parser.print_help()


if __name__ == "__main__":
    main()