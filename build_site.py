#!/usr/bin/env python3
"""Build the static photography site from immediate subfolders in photos/."""
from __future__ import annotations

import configparser
import html
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent
PHOTO_ROOT = ROOT / "photos"
OUTPUT = ROOT / "_site"
ASSETS = ROOT / "assets"
SETTINGS_FILE = ROOT / "content" / "site.ini"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Photo:
    source: Path
    filename: str
    full_path: str
    thumb_path: str
    width: int
    height: int
    thumb_width: int
    thumb_height: int
    alt: str


@dataclass
class Gallery:
    source_dir: Path
    slug: str
    title: str
    date_value: str
    date_display: str
    location: str
    description: str
    cover_name: str | None
    photos: list[Photo]


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower())
    return value.strip("-") or "gallery"


def infer_folder_metadata(folder: Path) -> tuple[str, str, str]:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})--(.+)$", folder.name)
    if match:
        raw_date, raw_title = match.groups()
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d")
            display = f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
            return readable_title(raw_title), raw_date, display
        except ValueError:
            pass
    return readable_title(folder.name), "", ""


def readable_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("-", " ").replace("_", " ")).strip()


def parse_gallery_metadata(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            values[key.strip().lower()] = value.strip()
    return values


def read_settings() -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)
    if not SETTINGS_FILE.is_file():
        raise FileNotFoundError(f"Missing configuration: {SETTINGS_FILE}")
    config.read(SETTINGS_FILE, encoding="utf-8")
    required = {
        "site": ("name", "photographer_name", "tagline", "location", "email"),
        "about": ("heading", "body"),
        "contact": ("heading", "intro"),
    }
    for section, keys in required.items():
        if not config.has_section(section):
            raise ValueError(f"Configuration is missing [{section}]")
        for key in keys:
            if not config.get(section, key, fallback="").strip():
                raise ValueError(f"Configuration value [{section}] {key} cannot be empty")
    return config


def optimize_image(source: Path, destination: Path, max_edge: int, quality: int) -> tuple[int, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode != "RGB":
            canvas = Image.new("RGB", image.size, "white")
            canvas.paste(image, mask=image.getchannel("A") if "A" in image.getbands() else None)
            image = canvas
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        # Saving a new WebP deliberately drops source EXIF, including GPS metadata.
        image.save(destination, "WEBP", quality=quality, method=6)
        return image.size


def make_alt(filename: str, title: str, index: int) -> str:
    stem = readable_title(Path(filename).stem)
    generic = re.match(r"^(cover|dsc|img|image|photo|pict)[ -_]?\d*$", stem, re.I)
    return f"{title}, photograph {index} of {{count}}" if generic or not stem else f"{stem} — {title}"


def build_gallery(folder: Path, slug: str, default_location: str) -> Gallery | None:
    images = sorted(
        (path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED),
        key=lambda path: natural_key(path.name),
    )
    if not images:
        print(f"WARNING: Skipping empty gallery folder: {folder.name}")
        return None

    inferred_title, inferred_date, inferred_display = infer_folder_metadata(folder)
    metadata = parse_gallery_metadata(folder / "gallery.txt")
    title = metadata.get("title", inferred_title)
    date_value = metadata.get("sort-date", inferred_date)
    date_display = metadata.get("date", inferred_display)
    location = metadata.get("location", default_location)
    description = metadata.get("description", f"Photographs from {title}.")
    generated = OUTPUT / "assets" / "images" / "generated" / slug
    photos: list[Photo] = []

    for index, source in enumerate(images, 1):
        target_name = f"{index:04d}.webp"
        full = generated / "full" / target_name
        thumb = generated / "thumb" / target_name
        try:
            width, height = optimize_image(source, full, 2400, 88)
            thumb_width, thumb_height = optimize_image(source, thumb, 800, 82)
        except (UnidentifiedImageError, OSError) as exc:
            print(f"WARNING: Skipping unreadable image {source}: {exc}")
            continue
        photos.append(Photo(
            source, source.name,
            f"assets/images/generated/{slug}/full/{target_name}",
            f"assets/images/generated/{slug}/thumb/{target_name}",
            width, height, thumb_width, thumb_height,
            make_alt(source.name, title, index),
        ))
    if not photos:
        print(f"WARNING: Skipping gallery with no readable photographs: {folder.name}")
        return None
    for photo in photos:
        photo.alt = photo.alt.format(count=len(photos))
    return Gallery(folder, slug, title, date_value, date_display, location, description,
                   metadata.get("cover"), photos)


def choose_cover(gallery: Gallery) -> Photo:
    if gallery.cover_name:
        exact = next((p for p in gallery.photos if p.filename.casefold() == gallery.cover_name.casefold()), None)
        if exact:
            return exact
        print(f"WARNING: Configured cover not found in {gallery.source_dir.name}: {gallery.cover_name}")
    return next((p for p in gallery.photos if p.source.stem.casefold().startswith("cover")), gallery.photos[0])


def rel(depth: int, target: str) -> str:
    return "../" * depth + target


def header(site_name: str, depth: int, current: str) -> str:
    def nav_link(label: str, target: str, key: str) -> str:
        active = ' aria-current="page"' if current == key else ""
        return f'<a href="{rel(depth, target)}"{active}>{label}</a>'
    return f'''<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header">
  <nav class="nav" aria-label="Primary navigation">
    <a class="brand" href="{rel(depth, '')}">{html.escape(site_name)}</a>
    <button class="nav-toggle" type="button" aria-label="Open navigation" aria-controls="primary-links" aria-expanded="false"><span></span></button>
    <div class="nav-links" id="primary-links">
      {nav_link("Home", "", "home")}
      {nav_link("About", "about/", "about")}
      {nav_link("Contact", "contact/", "contact")}
    </div>
  </nav>
</header>'''


def footer(site_name: str, location: str, depth: int) -> str:
    location_html = f"\n    <span>{html.escape(location)}</span>" if location else ""
    return f'''<footer class="site-footer">
  <div class="footer-inner">
    <span>&copy; <span data-year></span> {html.escape(site_name)}</span>{location_html}
  </div>
</footer>
<script src="{rel(depth, 'assets/js/main.js')}"></script>'''


def document(*, title: str, description: str, depth: int, body: str,
             og_image: str = "", page_type: str = "website") -> str:
    image_meta = f'\n  <meta property="og:image" content="{html.escape(rel(depth, og_image), quote=True)}">' if og_image else ""
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(description, quote=True)}">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:type" content="{page_type}">{image_meta}
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{rel(depth, 'assets/css/styles.css')}">
</head>
<body>
{body}
</body>
</html>
'''


def write_page(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def gallery_page(gallery: Gallery, site: configparser.SectionProxy) -> None:
    photos = []
    for index, photo in enumerate(gallery.photos, 1):
        photos.append(f'''<a class="photo" href="{rel(2, photo.full_path)}" data-full="{rel(2, photo.full_path)}" data-index="{index - 1}">
  <img src="{rel(2, photo.thumb_path)}" width="{photo.thumb_width}" height="{photo.thumb_height}" alt="{html.escape(photo.alt, quote=True)}" loading="lazy" decoding="async">
</a>''')
    # Dates and locations remain build metadata but are not displayed in galleries.
    facts = [f"{len(gallery.photos)} photograph{'s' if len(gallery.photos) != 1 else ''}"]
    facts_html = "".join(f"<span>{html.escape(item)}</span>" for item in facts)
    body = f'''{header(site["name"], 2, "")}
<main id="main">
  <section class="page-intro">
    <div class="container">
      <p class="eyebrow">Gallery</p>
      <h1>{html.escape(gallery.title)}</h1>
      <p class="lead">{html.escape(gallery.description)}</p>
    </div>
  </section>
  <section class="container" aria-label="{html.escape(gallery.title, quote=True)} photographs">
    <div class="gallery-facts">{facts_html}</div>
    <div class="photo-grid">{''.join(photos)}</div>
  </section>
</main>
{footer(site["name"], "", 2)}'''
    cover = choose_cover(gallery)
    write_page(OUTPUT / "galleries" / gallery.slug / "index.html", document(
        title=f"{gallery.title} — {site['name']}",
        description=gallery.description, depth=2, body=body,
        og_image=cover.full_path, page_type="article",
    ))


def main() -> int:
    config = read_settings()
    site, about, contact = config["site"], config["about"], config["contact"]
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    shutil.copytree(ASSETS, OUTPUT / "assets")
    (OUTPUT / ".nojekyll").write_text("", encoding="utf-8")
    PHOTO_ROOT.mkdir(exist_ok=True)

    folders = sorted((p for p in PHOTO_ROOT.iterdir() if p.is_dir()), key=lambda p: natural_key(p.name))
    slug_counts: dict[str, int] = {}
    galleries: list[Gallery] = []
    for folder in folders:
        title, date_value, _ = infer_folder_metadata(folder)
        base_slug = slugify(title)
        slug = base_slug
        if slug in slug_counts:
            suffix = date_value or slugify(folder.name)
            slug = f"{base_slug}-{suffix}"
            serial = 2
            while slug in slug_counts:
                slug = f"{base_slug}-{suffix}-{serial}"
                serial += 1
            print(f"WARNING: Duplicate gallery slug '{base_slug}'; using '{slug}'")
        slug_counts[slug] = 1
        gallery = build_gallery(folder, slug, site.get("location", ""))
        if gallery:
            galleries.append(gallery)
    galleries.sort(key=lambda g: (0 if g.date_value else 1, -(int(g.date_value.replace("-", "")) if g.date_value else 0), g.title.casefold()))

    for gallery in galleries:
        gallery_page(gallery, site)

    cards = []
    for gallery in galleries:
        cover = choose_cover(gallery)
        cards.append(f'''<a class="gallery-card" href="galleries/{gallery.slug}/">
  <div class="gallery-cover"><img src="{cover.thumb_path}" width="{cover.thumb_width}" height="{cover.thumb_height}" alt="Cover photograph for {html.escape(gallery.title, quote=True)}" loading="lazy" decoding="async"></div>
  <div class="gallery-meta">
    <div><h3>{html.escape(gallery.title)}</h3></div>
    <span>{len(gallery.photos)} photo{'s' if len(gallery.photos) != 1 else ''}</span>
  </div>
</a>''')
    listing = f'<div class="gallery-list">{"".join(cards)}</div>' if cards else (
        '<p class="empty-state">No galleries yet. Add a folder of photographs inside <strong>photos/</strong>.</p>'
    )
    home_body = f'''{header(site["name"], 0, "home")}
<main id="main">
  <section class="hero">
    <div class="container hero-grid">
      <div><p class="eyebrow">{html.escape(site.get("category", "Photography"))}</p><h1>{html.escape(site["photographer_name"])}</h1></div>
      <div><p class="hero-copy">{html.escape(site["tagline"])}</p><p class="hero-location">{html.escape(site["location"])}</p></div>
    </div>
  </section>
  <section class="section" aria-labelledby="galleries-title"><div class="container">
    <div class="section-header"><h2 id="galleries-title">Galleries</h2><p>Recent events, people, and moments.</p></div>
    {listing}
  </div></section>
</main>
{footer(site["name"], site["location"], 0)}'''
    home_cover = choose_cover(galleries[0]).full_path if galleries else ""
    write_page(OUTPUT / "index.html", document(
        title=site["name"], description=site["tagline"], depth=0, body=home_body, og_image=home_cover,
    ))

    about_body = f'''{header(site["name"], 1, "about")}
<main id="main">
  <section class="page-intro"><div class="container"><p class="eyebrow">About</p><h1>{html.escape(about["heading"])}</h1></div></section>
  <section class="container prose-grid">
    <p class="prose-label">The photographer</p>
    <div class="prose">{"".join(f"<p>{html.escape(p.strip())}</p>" for p in re.split(r"\\n\\s*\\n", about["body"].strip()) if p.strip())}
      <dl class="about-details"><div><dt>Based in</dt><dd>{html.escape(site["location"])}</dd></div><div><dt>Focus</dt><dd>{html.escape(about.get("focus", "Events, portraits, and documentary photography"))}</dd></div></dl>
    </div>
  </section>
</main>
{footer(site["name"], site["location"], 1)}'''
    write_page(OUTPUT / "about" / "index.html", document(
        title=f"About — {site['name']}", description=f"About {site['photographer_name']}.", depth=1, body=about_body,
    ))

    instagram_url = site.get("instagram_url", "")
    contact_body = f'''{header(site["name"], 1, "contact")}
<main id="main">
  <section class="page-intro contact-intro"><div class="container">
    <p class="eyebrow">Contact</p><h1>{html.escape(contact["heading"])}</h1>
    <p class="lead">{html.escape(contact["intro"])}</p>
    <div class="contact-options">
      <a class="contact-card" href="mailto:{quote(site['email'], safe='@.+-')}"><span>Email</span><strong>{html.escape(site["email"])}</strong></a>

#   HERE IS THE INSTAGRAM THING, DETE THIS TO GET RID OF IT, if you want to change the url / name, change it in sites.ini  <a class="contact-card" href="{html.escape(instagram_url, quote=True)}" target="_blank" rel="noopener noreferrer"><span>Instagram</span><strong>{html.escape(site.get("instagram_username", "@yourusername"))}</strong></a>
      <div class="contact-card"><span>Location</span><strong>{html.escape(site["location"])}</strong></div>
    </div>
  </div></section>
</main>
{footer(site["name"], site["location"], 1)}'''
    write_page(OUTPUT / "contact" / "index.html", document(
        title=f"Contact — {site['name']}", description=contact["intro"], depth=1, body=contact_body,
    ))
    count = sum(len(g.photos) for g in galleries)
    print(f"Built Home, About, Contact, {len(galleries)} galleries, and {count} photographs into {OUTPUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        raise
