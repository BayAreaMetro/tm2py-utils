# Documentation

This directory contains the documentation for tm2py-utils, built with MkDocs and deployed to GitHub Pages.

## Building Locally

### Prerequisites

```bash
pip install mkdocs mkdocs-material pymdown-extensions mkdocs-git-revision-date-localized-plugin
```

### Serve Locally

```bash
# From repository root
mkdocs serve
```

Visit http://localhost:8000

### Build Static Site

```bash
mkdocs build
```

Output in `site/` directory.

## Documentation Structure

```
docs/
├── index.md              # Homepage
├── install.md            # Installation guide
├── dashboard.md          # Dashboard usage
├── summaries.md          # Summary generation
├── configuration.md      # Configuration reference
├── contributing.md       # Development guide
├── css/
│   └── extra.css        # Custom styles
└── README.md            # This file
```

## Deployment

Documentation is automatically deployed to GitHub Pages when changes are pushed to the main branch.

### Manual Deployment

```bash
# Build and deploy
mkdocs gh-deploy
```

This builds the site and pushes to the `gh-pages` branch.

## Writing Documentation

### Markdown Extensions

Documentation uses Material for MkDocs with these extensions:

**Admonitions:**
```markdown
!!! note "Optional Title"
    Content here
```

**Code Blocks:**
```markdown
```python
def example():
    pass
\```
```

**Tabs:**
```markdown
=== "Tab 1"
    Content 1

=== "Tab 2"
    Content 2
```

**Tables:**
```markdown
| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
```

### Adding Pages

1. Create `.md` file in `docs/`
2. Add to `nav` section in `mkdocs.yml`
3. Test locally with `mkdocs serve`
4. Commit and push

## Maintenance

- Update installation instructions when dependencies change
- Keep dashboard tab documentation in sync with YAML files
- Add examples for new summary types
- Update configuration reference when adding new options

## Related Files

- `mkdocs.yml` - MkDocs configuration (in repository root)
- `requirements.txt` - Documentation build dependencies
- `.github/workflows/docs.yml` - CI/CD for documentation (if configured)
