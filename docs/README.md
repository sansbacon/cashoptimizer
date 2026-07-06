# Documentation

This directory contains source documentation for the cash-optimizer project, built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Structure

```
docs/
├── source/              # Documentation source files
│   ├── index.md         # Homepage
│   ├── getting-started.md
│   ├── guides/
│   │   ├── cli.md       # CLI command reference
│   │   ├── gui.md       # Desktop GUI guide
│   │   ├── python-api.md
│   │   └── governance.md
│   └── api/
│       └── reference.md  # API reference
├── build/               # Generated static site (git-ignored)
└── README.md            # This file
```

## Building Locally

### Install Dependencies

```bash
# Option 1: From docs requirements
pip install -r docs-requirements.txt

# Option 2: From project docs extra
pip install -e ".[docs]"
```

### Build Site

```bash
# Using MkDocs directly
mkdocs build -f zensical.yaml -d docs/build

# Or using the Zensical config
mkdocs build -f zensical.yaml
```

### Live Server

During development, run a local server that auto-reloads:

```bash
mkdocs serve -f zensical.yaml
```

Visit `http://localhost:8000` in your browser.

## Deploying to GitHub Pages

The documentation automatically deploys to GitHub Pages when you push to `main`:

1. Push changes to `docs/source/` or `zensical.yaml`
2. GitHub Actions workflow `.github/workflows/deploy-docs.yml` runs
3. MkDocs builds the static site
4. Site deploys to GitHub Pages
5. Available at `https://yourusername.github.io/cash_optimizer/`

### Enable GitHub Pages

1. Go to repository Settings → Pages
2. Under "Build and deployment", select:
   - **Source**: GitHub Actions
   - **Branch**: main (automatic via workflow)

## Configuration

### zensical.yaml

Main MkDocs configuration file at project root:

```yaml
site_name: cash-optimizer
docs_dir: docs/source
build_dir: docs/build
site_url: https://EricTruett.github.io/cash_optimizer/
```

Key sections:
- `theme`: Material theme with specific features
- `nav`: Navigation structure and links
- `plugins`: Search, social cards
- `markdown_extensions`: Code highlighting, tables, etc.

### Navigation

Edit the `nav` section in `zensical.yaml` to add/remove pages or reorder:

```yaml
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Guides:
    - CLI: guides/cli.md
    - Python API: guides/python-api.md
  - API Reference: api/reference.md
```

## Writing Documentation

### File Format

All documentation is in Markdown (`.md`). Key guidelines:

- Use `# H1` for page title
- Use `## H2` for sections
- Code blocks with syntax highlighting:
  ```python
  from cash_optimizer import CashOptimizer
  ```
- Admonitions:
  ```markdown
  !!! note
      This is a note
  ```
- Links to other pages:
  ```markdown
  [Getting Started](getting-started.md)
  [CLI Guide](guides/cli.md)
  ```

### Adding a New Page

1. Create `.md` file in `docs/source/` (or subdirectory)
2. Add to `nav` section in `zensical.yaml`
3. Run `mkdocs serve` to see it live
4. Push to trigger deploy

Example:

```bash
# Create new guide
echo "# Troubleshooting" > docs/source/guides/troubleshooting.md

# Edit zensical.yaml to add:
# - Troubleshooting: guides/troubleshooting.md
```

## Linking to Specifications

Reference specification files from main directory:

```yaml
nav:
  - Specifications:
    - Project: specs/cash_optimizer_spec.md
    - CLI: specs/cli_spec.md
    - GUI: specs/gui_spec.md
```

Or in Markdown:

```markdown
See the [Project Specification](../specs/cash_optimizer_spec.md)
```

Note: Use `../` to traverse up from `docs/source/`.

## GitHub Pages URL

After deployment, access docs at:

```
https://EricTruett.github.io/cash_optimizer/
```

To use a custom domain:

1. Add `CNAME` file to repo root with your domain
2. Configure DNS CNAME to `username.github.io`
3. Update `site_url` in `zensical.yaml`

## Troubleshooting

### Build Fails: "Module not found"

Install dependencies:

```bash
pip install -r docs-requirements.txt
```

### Changes Not Showing in Live Server

Restart `mkdocs serve`:

```bash
Ctrl+C  # Stop server
mkdocs serve -f zensical.yaml  # Restart
```

### GitHub Pages Not Updating

1. Check workflow at `.github/workflows/deploy-docs.yml`
2. Go to Actions tab to see build status
3. Verify Pages settings: Settings → Pages → Source is "GitHub Actions"

## Building Docs in CI/CD

The workflow is configured to build and deploy automatically:

```yaml
# .github/workflows/deploy-docs.yml
on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'zensical.yaml'
```

Triggers on:
- Push to `main` branch
- Changes to `docs/` or `zensical.yaml`
- Manual workflow dispatch

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material Theme Guide](https://squidfunk.github.io/mkdocs-material/)
- [Markdown Guide](https://www.markdownguide.org/)
- [GitHub Pages Docs](https://docs.github.com/en/pages)

## Contributing

When updating documentation:

1. Create a branch: `git checkout -b docs/update-cli-guide`
2. Edit `.md` files in `docs/source/`
3. Test locally: `mkdocs serve -f zensical.yaml`
4. Commit and push
5. Submit PR for review
6. Merge to `main` to auto-deploy

---

**Last Updated**: 2024 | **Built with**: MkDocs Material
