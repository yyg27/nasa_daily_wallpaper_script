#!/usr/bin/env python3
"""A small daily notification with NASA's picture of the day."""
import argparse
import html
import json
import locale
import os
import random
import re
import shutil
import subprocess
import sys
import time
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
# Pictures older than this are deleted, except favorites and the current wallpaper.
KEEP_DAYS = 7
SEARCH_TERMS = ["nebula", "galaxy", "hubble", "webb telescope", "aurora", "saturn", "jupiter", "earth from orbit"]

STRINGS = {
    "en": {
        "set": "Set as wallpaper",
        "favorite": "Favorite",
        "details": "Details",
        "ok": "OK",
        "saved": "Saved to favorites",
        "no_latest": "No picture shown yet",
        "no_photos": "No wallpaper-sized photos in this search, try again",
        "api_error": "NASA API error",
        "network_error": "Network error",
        "timed_out": "timed out",
        "gallery": "NASA favorites",
        "open": "Open on NASA",
    },
    "tr": {
        "set": "Duvar kâğıdı yap",
        "favorite": "Favorilere ekle",
        "details": "Ayrıntılar",
        "ok": "Tamam",
        "saved": "Favorilere eklendi",
        "no_latest": "Henüz bir resim gösterilmedi",
        "no_photos": "Bu aramada duvar kâğıdına uygun fotoğraf yok, tekrar deneyin",
        "api_error": "NASA API hatası",
        "network_error": "Ağ hatası",
        "timed_out": "zaman aşımı",
        "gallery": "NASA favorileri",
        "open": "NASA'da aç",
    },
}


def language():
    lang = os.environ.get("NASA_WALLPAPER_LANG") or locale.getlocale()[0] or ""
    # Windows reports names like "Turkish_Türkiye" instead of "tr_TR".
    return "tr" if lang.lower().startswith(("tr", "turkish")) else "en"


T = STRINGS[language()]


def pictures_dir():
    try:
        out = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, check=True)
        return Path(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path.home() / "Pictures"


PHOTOS = pictures_dir() / "NasaPhotos"
FAVORITES = PHOTOS / "favorites"
CURRENT = PHOTOS / "current.txt"  # wallpaper set by this script
LATEST = PHOTOS / "latest.txt"  # last picture shown in a notification


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
        raise RuntimeError(T["no_photos"])
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

    for name, label in (actions or {"ok": T["ok"]}).items():
        tk.Button(row, text=label, command=lambda n=name: pick(n)).pack(side="left", padx=4)
    root.mainloop()
    return choice


def notify(title, body, icon=None, actions=None, replace_id=None):
    """Show (or update) a notification. Returns (notification id, clicked action or None)."""
    if not shutil.which("notify-send"):
        try:
            return None, dialog(title, body, actions)
        except ImportError:
            print(f"{title}\n{body}")
            return None, None
    # resident: GNOME keeps the notification open after a button is clicked.
    cmd = ["notify-send", "--app-name=NASA Wallpaper", "--print-id", "--hint=boolean:resident:true", title, body]
    if icon:
        cmd.append(f"--icon={icon}")
    if replace_id:
        cmd.append(f"--replace-id={replace_id}")
    cmd += [f"--action={name}={label}" for name, label in (actions or {}).items()]
    try:
        # Unanswered notifications would otherwise keep the service busy into the next day.
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=6 * 3600)
    except subprocess.TimeoutExpired:
        return replace_id, None
    lines = out.stdout.split()
    return (lines[0] if lines else None), (lines[1] if len(lines) > 1 else None)


def offer(path):
    """Notify about a picture and act on the clicked button."""
    LATEST.write_text(str(path))
    entry = metadata(path)
    actions = {"details": T["details"], "favorite": T["favorite"], "set": T["set"]}
    body = entry["explanation"]
    if len(body) > 200:
        body = body[:200].rsplit(" ", 1)[0] + "…"
    # Re-show the notification after each click until it's dismissed or the wallpaper is set.
    notification_id = None
    while True:
        notification_id, choice = notify(entry["title"], body, path, actions, notification_id)
        if choice is None:
            break
        if choice == "set":
            set_wallpaper(path)
            close_notification(notification_id)
            break
        if choice == "favorite":
            favorite(path)
            del actions["favorite"]
        elif choice == "details":
            webbrowser.open(entry["link"])


def close_notification(notification_id):
    if notification_id:
        subprocess.run(["gdbus", "call", "--session", "--dest=org.freedesktop.Notifications",
                        "--object-path=/org/freedesktop/Notifications",
                        "--method=org.freedesktop.Notifications.CloseNotification", notification_id],
                       capture_output=True)


def favorite(path):
    if path.parent != FAVORITES:
        FAVORITES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, FAVORITES)
        shutil.copy2(path.with_suffix(".json"), FAVORITES)
        write_gallery()


def write_gallery():
    """Regenerate favorites/index.html: every favorite with its picture and full explanation."""
    images = {f.stem: f.name for f in FAVORITES.iterdir() if f.suffix not in (".json", ".html")}
    cards = []
    for meta in sorted(FAVORITES.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        entry = json.loads(meta.read_text())
        image = urllib.parse.quote(images.get(meta.stem, ""))
        link = entry.get("link", "")
        # The link ends up in an href, so only allow web links.
        link = f'<a href="{html.escape(link)}">{T["open"]}</a>' if link.startswith(("https://", "http://")) else ""
        cards.append(f"""<article>
<a href="{image}"><img src="{image}" alt="" loading="lazy"></a>
<h2>{html.escape(entry["title"])}</h2>
<p>{html.escape(entry.get("explanation", ""))}</p>
{link}
</article>""")
    (FAVORITES / "index.html").write_text(f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{T["gallery"]}</title>
<style>
body {{ background: #0b0d12; color: #dde; font: 16px/1.6 system-ui, sans-serif; max-width: 960px; margin: auto; padding: 16px; }}
img {{ width: 100%; border-radius: 8px; }}
article {{ margin-bottom: 48px; }}
a {{ color: #8ab4ff; }}
</style>
<h1>{T["gallery"]}</h1>
{"".join(cards)}
""")


def cleanup():
    """Delete pictures older than KEEP_DAYS, keeping the current wallpaper and the last shown picture."""
    if not PHOTOS.is_dir():
        return
    keep = {Path(f.read_text()).stem for f in (CURRENT, LATEST) if f.exists()}
    cutoff = time.time() - KEEP_DAYS * 86400
    for f in PHOTOS.iterdir():
        if f.is_file() and f.suffix != ".txt" and f.stem not in keep and f.stat().st_mtime < cutoff:
            f.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="today", choices=["today", "random", "favorite"],
                        help="today: show today's picture (default); random: show a random NASA photo; "
                             "favorite: save the last shown picture to favorites")
    args = parser.parse_args()

    try:
        if args.command == "favorite":
            if not LATEST.exists():
                sys.exit(T["no_latest"])
            path = Path(LATEST.read_text())
            favorite(path)
            notify(T["saved"], metadata(path)["title"], path)
        else:
            # Cleanup first, so an old copy of a picture that is offered again gets downloaded fresh.
            cleanup()
            offer(download((apod_today() or iotd_latest()) if args.command == "today" else library_random()))
    except urllib.error.HTTPError as e:
        sys.exit(f"{T['api_error']} {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        sys.exit(f"{T['network_error']}: {e.reason}")
    except TimeoutError:
        sys.exit(f"{T['network_error']}: {T['timed_out']}")


if __name__ == "__main__":
    main()
