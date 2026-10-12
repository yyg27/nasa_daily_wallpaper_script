#!/usr/bin/env python3
"""NASA's picture of the day as a desktop notification and wallpaper."""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

APOD_URL = "https://api.nasa.gov/planetary/apod"
IOTD_FEED = "https://www.nasa.gov/feeds/iotd-feed/"
LIBRARY_URL = "https://images-api.nasa.gov/search"
# DEMO_KEY is rate limited per IP but plenty for a few requests a day.
API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")
SEARCH_TERMS = ["nebula", "galaxy", "hubble", "webb telescope", "aurora", "saturn", "jupiter", "earth from orbit"]


def pictures_dir():
    try:
        out = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, check=True)
        return Path(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path.home() / "Pictures"


PHOTOS = pictures_dir() / "NasaPhotos"
FAVORITES = PHOTOS / "favorites"
CURRENT = PHOTOS / "current.txt"


def get_json(url, **params):
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=30) as res:
        return json.load(res)


def apod_today():
    """Today's APOD, or None on video days or when the API is broken."""
    try:
        entry = get_json(APOD_URL, api_key=API_KEY)
    except urllib.error.HTTPError:
        return None
    image = entry.get("hdurl") or entry.get("url", "")
    # Since APOD moved to science.nasa.gov the API returns the NASA logo instead of the picture.
    if entry.get("media_type") != "image" or "nasa-logo" in image:
        return None
    date = entry["date"]
    return {
        "id": f"apod_{date}",
        "title": entry["title"],
        "explanation": entry["explanation"],
        "image": image,
        "link": f"https://apod.nasa.gov/apod/ap{date[2:].replace('-', '')}.html",
    }


def iotd_latest():
    """Latest entry of NASA's Image of the Day feed."""
    with urllib.request.urlopen(IOTD_FEED, timeout=30) as res:
        item = ET.parse(res).getroot().find("channel/item")
    date = parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
    return {
        "id": f"iotd_{date}",
        "title": item.findtext("title"),
        "explanation": re.sub(r"<[^>]+>", "", item.findtext("description") or ""),
        "image": item.find("enclosure").get("url"),
        "link": item.findtext("link"),
    }


def library_random():
    """A random wallpaper-sized space photo from the NASA Image Library."""
    data = get_json(LIBRARY_URL, q=random.choice(SEARCH_TERMS), media_type="image", page_size=100)
    candidates = []
    for item in data["collection"]["items"]:
        images = [l for l in item.get("links", []) if l.get("render") == "image"]
        best = max(images, key=lambda l: l.get("width", 0), default=None)
        if best and best.get("width", 0) >= 1920 and best["width"] > best.get("height", 0):
            candidates.append((item["data"][0], best["href"]))
    if not candidates:
        raise RuntimeError("No wallpaper-sized photos in this search, try again")
    meta, image = random.choice(candidates)
    return {
        "id": f"nasa_{meta['nasa_id']}",
        "title": meta["title"],
        "explanation": meta.get("description", ""),
        "image": image,
        "link": f"https://images.nasa.gov/details/{meta['nasa_id']}",
    }


def download(entry):
    """Save the image next to its metadata, skipping the download if it already exists."""
    suffix = Path(urllib.parse.urlparse(entry["image"]).path).suffix or ".jpg"
    path = PHOTOS / f"{entry['id']}{suffix}"
    if not path.exists():
        PHOTOS.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".part")
        with urllib.request.urlopen(entry["image"], timeout=60) as res, open(part, "wb") as f:
            shutil.copyfileobj(res, f)
        part.replace(path)
    path.with_suffix(".json").write_text(json.dumps(entry))
    return path


def metadata(path):
    return json.loads(path.with_suffix(".json").read_text())


def set_wallpaper(path):
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
    else:
        for key in ("picture-uri", "picture-uri-dark"):
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", key, path.as_uri()], check=True)
    CURRENT.write_text(str(path))


def dialog(title, body, actions):
    """Fallback for systems without notify-send (Windows): a small always-on-top window."""
    import tkinter as tk
    choice = None
    root = tk.Tk()
    root.title("NASA Wallpaper")
    root.attributes("-topmost", True)
    tk.Label(root, text=title, font=("TkDefaultFont", 12, "bold"), wraplength=420, justify="left").pack(
        padx=16, pady=(16, 4), anchor="w")
    tk.Label(root, text=body, wraplength=420, justify="left").pack(padx=16, anchor="w")
    row = tk.Frame(root)
    row.pack(padx=16, pady=16, anchor="e")

    def pick(name):
        nonlocal choice
        choice = name
        root.destroy()

    for name, label in (actions or {"ok": "OK"}).items():
        tk.Button(row, text=label, command=lambda n=name: pick(n)).pack(side="left", padx=4)
    root.mainloop()
    return choice


def notify(title, body, icon=None, actions=None):
    """Show a notification and return the clicked action name, if any."""
    if not shutil.which("notify-send"):
        try:
            return dialog(title, body, actions)
        except ImportError:
            print(f"{title}\n{body}")
            return None
    cmd = ["notify-send", "--app-name=NASA Wallpaper", title, body]
    if icon:
        cmd.append(f"--icon={icon}")
    cmd += [f"--action={name}={label}" for name, label in (actions or {}).items()]
    try:
        # Unanswered notifications would otherwise keep the service busy into the next day.
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=6 * 3600)
    except subprocess.TimeoutExpired:
        return None
    return out.stdout.strip() or None


def offer(path, auto):
    """Notify about a picture and act on the clicked button."""
    entry = metadata(path)
    actions = {"favorite": "Favorite", "details": "Details"}
    if auto:
        set_wallpaper(path)
    else:
        actions = {"set": "Set as wallpaper", **actions}
    body = entry["explanation"]
    if len(body) > 200:
        body = body[:200].rsplit(" ", 1)[0] + "…"
    choice = notify(entry["title"], body, path, actions)
    if choice == "set":
        set_wallpaper(path)
    elif choice == "favorite":
        favorite(path)
    elif choice == "details":
        webbrowser.open(entry["link"])


def favorite(path):
    if path.parent != FAVORITES:
        FAVORITES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, FAVORITES)
        shutil.copy2(path.with_suffix(".json"), FAVORITES)
    notify("Saved to favorites", metadata(path)["title"], path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="today", choices=["today", "skip", "favorite"],
                        help="today: offer today's picture (default); skip: random NASA photo as wallpaper; "
                             "favorite: save the current wallpaper to favorites")
    parser.add_argument("--auto", action="store_true", help="set today's picture without asking")
    args = parser.parse_args()

    try:
        if args.command == "today":
            offer(download(apod_today() or iotd_latest()), args.auto)
        elif args.command == "skip":
            offer(download(library_random()), auto=True)
        elif not CURRENT.exists():
            sys.exit("No wallpaper set by this script yet")
        else:
            favorite(Path(CURRENT.read_text()))
    except urllib.error.HTTPError as e:
        sys.exit(f"NASA API error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error: {e.reason}")
    except TimeoutError:
        sys.exit("Network error: timed out")


if __name__ == "__main__":
    main()
