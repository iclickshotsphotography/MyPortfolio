# Automatic Photography Portfolio

A minimal photography website for GitHub Pages. The build discovers photo folders and automatically creates the Home gallery list and a full page for every gallery. Normal gallery management requires no HTML, CSS, JavaScript, terminal, or local setup.

## Initial setup

1. Create a GitHub repository.
2. Upload this entire project to the repository root and commit it to the `main` branch.
3. Open **Settings → Pages** in the repository.
4. Under **Build and deployment**, choose **GitHub Actions** as the source.
5. Edit [`content/site.ini`](content/site.ini) to replace the placeholder identity and contact details.
6. Open **Actions → Build and deploy photography site → Run workflow** to trigger the first build (a push to `main` also triggers it).
7. Wait for the green deployment check. The site will appear at either `https://USERNAME.github.io/` or `https://USERNAME.github.io/REPOSITORY-NAME/`.

The generated site uses relative links, so both GitHub Pages URL forms work.

## Add a gallery without code

1. Open the `photos` folder on GitHub.
2. Select **Add file → Upload files**.
3. Upload a folder named `YYYY-MM-DD--Gallery-Title`.
4. Add the photographs.
5. Commit the files.
6. Wait for the GitHub Actions deployment.

Example: `2026-08-22--Graduation-Party` becomes **Graduation Party**, dated **August 22, 2026**. Dated galleries appear newest first. A folder without a date is still built and appears after all dated galleries.

> GitHub’s web interface may flatten a dragged folder in some browsers. If so, create the gallery folder first (for example by creating a temporary file inside it), then open that folder and upload the photographs. GitHub Desktop is convenient for large batches.

### Add more photographs

Open the existing folder under `photos`, select **Add file → Upload files**, add the photographs, and commit. The next deployment updates the page and count.

### Delete a gallery

Delete its entire folder under `photos` and commit the deletion. The next deployment removes its card, page, and generated images.

### Select the cover

A filename beginning with `cover` (case-insensitive) becomes the cover, such as `cover.jpg`, `cover-main.webp`, or `Cover.jpeg`. If none exists, the first photograph in natural filename order is used. The cover remains visible in the gallery.

### Control photograph order

Photographs use natural numeric ordering, so `1.jpg`, `2.jpg`, `3.jpg`, `10.jpg` appear correctly. Numbered filenames are recommended for predictable placement:

```text
01.jpg
02.jpg
03.jpg
```

### Optional per-gallery details

The folder name is enough. Optionally add `gallery.txt` inside one gallery:

```text
title: Graduation Party
date: August 22, 2026
sort-date: 2026-08-22
location: Jersey City, NJ
description: Portraits and candid photographs from the celebration.
cover: IMG_1842.jpg
```

## Edit Home, About, and Contact content

Edit only [`content/site.ini`](content/site.ini). It controls:

- site title and photographer name;
- Home category and tagline;
- biography, approach, and photography focus;
- email and Instagram profile;
- location;
- Contact page heading and booking message;
- shared header, footer, and metadata content.

The shipped email (`your-email@example.com`) and Instagram (`@yourusername`) are placeholders and must be replaced. The configuration is public: never add passwords, API keys, or secrets.

## Supported images and practical limits

The builder accepts `.jpg`, `.jpeg`, `.png`, and `.webp` with uppercase or lowercase extensions. It ignores other files such as `.DS_Store`, `Thumbs.db`, and `README.md`. Empty gallery folders produce a warning and do not stop the build.

GitHub’s browser uploader limits each file to 25 MiB and accepts up to 100 files at once. Use compressed web-ready images, split larger uploads, or use GitHub Desktop. Keep the original full-resolution archive somewhere else.

During deployment, Pillow:

- corrects EXIF orientation;
- creates an approximately 800 px thumbnail and a 2400 px gallery image without upscaling;
- converts public copies to WebP;
- writes fresh files without source EXIF, removing GPS metadata;
- includes dimensions to prevent layout shift.

Source photographs remain only in `photos/`; generated output is not committed.

## How deployment works

The workflow at [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs on every push to `main` and manually through `workflow_dispatch`. It installs Pillow, runs `build_site.py`, uploads the clean `_site` directory, and deploys it using the official GitHub Pages actions.

## Optional local preview

Advanced users can preview locally:

```bash
python -m pip install -r requirements.txt
python build_site.py
python -m http.server 8000 -d _site
```

Open `http://localhost:8000/`. Generated `_site/` output is ignored by Git.
