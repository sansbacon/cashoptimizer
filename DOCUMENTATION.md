# Documentation Setup Guide

This project uses **Zensical** (MkDocs Material) for documentation that deploys to GitHub Pages.

## Quick Start

### Local Development

```bash
# Install documentation dependencies
pip install -r docs-requirements.txt

# Or from project extras
pip install -e ".[docs]"

# Build documentation
mkdocs build -f zensical.yaml

# Or serve locally with live reload
mkdocs serve -f zensical.yaml
```

Then open `http://localhost:8000` in your browser.

### Windows Batch Script

```bash
build-docs.bat
```

### Linux/Mac Shell Script

```bash
chmod +x build-docs.sh
./build-docs.sh
```

## Documentation Structure

```
docs/
├── source/
│   ├── index.md                          # Homepage
│   ├── getting-started.md                # Installation & setup
│   ├── guides/
│   │   ├── cli.md                        # CLI command reference
│   │   ├── gui.md                        # Desktop application guide
│   │   ├── python-api.md                 # Library API reference
│   │   └── governance.md                 # Governance automation guide
│   └── api/
│       └── reference.md                  # Detailed API reference
├── build/                                # Generated static site (git-ignored)
└── README.md                             # Docs build instructions

zensical.yaml                             # Main MkDocs config
docs-requirements.txt                     # Documentation dependencies
build-docs.sh                             # Linux/Mac build script
build-docs.bat                            # Windows build script
```

## Publishing to GitHub Pages

### Automatic (Recommended)

Documentation automatically deploys when you push to `main`:

1. **Workflow**: `.github/workflows/deploy-docs.yml`
2. **Triggers**: 
   - Push to `main` branch
   - Changes to `docs/` folder or `zensical.yaml`
3. **Output**: Available at `https://username.github.io/cash_optimizer/`

### Enable GitHub Pages (One-Time Setup)

1. Go to repository **Settings** → **Pages**
2. Set:
   - **Source**: GitHub Actions
   - **Branch**: main (automatic)
3. Save

### Manual Deployment

If you prefer manual control:

```bash
# Build locally
mkdocs build -f zensical.yaml -d docs/build

# Deploy to GitHub Pages (if configured)
mkdocs gh-deploy -f zensical.yaml
```

## Editing Documentation

### Add a New Page

1. Create `.md` file in `docs/source/`:

```bash
touch docs/source/guides/my-guide.md
```

2. Edit the file with Markdown content

3. Add to navigation in `zensical.yaml`:

```yaml
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Guides:
    - CLI: guides/cli.md
    - My Guide: guides/my-guide.md      # <- Add this
```

4. Test locally:

```bash
mkdocs serve -f zensical.yaml
```

5. Push to `main` to auto-deploy

### Markdown Syntax

Use standard Markdown with Material theme extensions:

```markdown
# Page Title

## Section

### Subsection

Text with **bold** and *italic*.

#### Code Block

\`\`\`python
from cash_optimizer import CashOptimizer
optimizer = CashOptimizer(players)
\`\`\`

#### Lists

- Item 1
- Item 2
  - Nested item

#### Links

[Link text](../other-page.md)
[External](https://example.com)

#### Admonitions

!!! note
    This is a note

!!! warning
    This is a warning

!!! tip
    This is a helpful tip

#### Tables

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
```

### Linking Between Pages

Within docs folder hierarchy:

```markdown
# Link to getting started (same level)
[Install](getting-started.md)

# Link to CLI guide (in guides subfolder)
[CLI Reference](guides/cli.md)

# Link to spec files (up and out to specs)
[Project Spec](../specs/cash_optimizer_spec.md)
```

### Navigation Structure

Edit `nav` section in `zensical.yaml`:

```yaml
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Guides:
    - CLI: guides/cli.md
    - GUI: guides/gui.md
    - Python API: guides/python-api.md
    - Governance: guides/governance.md
  - API Reference: api/reference.md
  - Specifications:
    - Project Spec: ../specs/cash_optimizer_spec.md
    - CLI Spec: ../specs/cli_spec.md
    - GUI Spec: ../specs/gui_spec.md
```

Indent to create subsections (Guides, Specifications, etc.)

## Configuration

### zensical.yaml Options

```yaml
site_name: cash-optimizer              # Site title
site_url: https://yourdomain.com/      # Deployment URL
docs_dir: docs/source                  # Source directory
build_dir: docs/build                  # Output directory

theme:
  name: material                        # Use Material theme
  logo: assets/logo.png                # Logo file (optional)
  features:
    - navigation.instant               # Instant loading
    - search.highlight                 # Search highlighting

plugins:
  - search                             # Full-text search
  - social                             # Social preview cards

markdown_extensions:
  - admonition                         # !!! admonition syntax
  - pymdownx.details                   # Collapsible sections
  - pymdownx.highlight                 # Code highlighting
```

### Theme Customization

Add `docs/overrides/` for custom styling:

```
docs/
├── overrides/
│   ├── main.html                      # Override base template
│   ├── 404.html                       # Custom 404 page
│   └── assets/
│       └── stylesheets/
│           └── custom.css             # Custom CSS
└── source/
```

Reference in `zensical.yaml`:

```yaml
theme:
  custom_dir: docs/overrides
```

## Troubleshooting

### Build Fails: "Module not found"

```bash
pip install -r docs-requirements.txt
```

### Changes Not Showing

Restart the server:

```bash
# Stop: Ctrl+C
# Restart:
mkdocs serve -f zensical.yaml
```

### GitHub Pages Not Updating

1. Check workflow status: **Actions** tab
2. Verify Pages setting: **Settings** → **Pages** → Source is "GitHub Actions"
3. Check for build errors in workflow logs

### Port Already in Use

```bash
# Use different port
mkdocs serve -f zensical.yaml -a localhost:8001
```

## Advanced Usage

### Build and Deploy Script

```bash
#!/bin/bash
# Deploy to GitHub Pages

mkdocs build -f zensical.yaml
mkdocs gh-deploy -f zensical.yaml
```

### CI/CD Integration

The `.github/workflows/deploy-docs.yml` workflow:

1. Triggers on push to `main`
2. Installs dependencies
3. Builds with MkDocs
4. Uploads to GitHub Pages
5. Deploys automatically

View logs in **Actions** tab.

### Custom Domain

1. Create `CNAME` file in repo root:

```
yourdomain.com
```

2. Update `site_url` in `zensical.yaml`

3. Configure DNS CNAME pointing to `username.github.io`

### Search Configuration

Full-text search is enabled via the `search` plugin. No additional setup needed.

To customize search:

```yaml
plugins:
  - search:
      lang: en
      separator: '[\s\-\.]+'
```

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [Markdown Guide](https://www.markdownguide.org/)
- [GitHub Pages Docs](https://docs.github.com/en/pages)

## Contributing Documentation

1. Create feature branch:

```bash
git checkout -b docs/update-api-guide
```

2. Make changes to `docs/source/` or `zensical.yaml`

3. Test locally:

```bash
mkdocs serve -f zensical.yaml
```

4. Commit and push:

```bash
git add docs/ zensical.yaml
git commit -m "docs: update API guide with new examples"
git push origin docs/update-api-guide
```

5. Open pull request for review

6. Merge to `main` - documentation auto-deploys!

---

**Questions?** Check the [docs README](docs/README.md) or review existing documentation pages for examples.
