# antientropy-mcp

MCP server for searching and reading articles from the [AntiEntropy Resource Portal](https://resourceportal.antientropy.org/docs). Gives Claude Code (or any MCP client) access to 140+ articles on nonprofit governance, compliance, HR policies, and fiscal sponsorship.

## Tools

- **antientropy_glob** — find articles by title/category path (`*policy*`, `Governance*/**`)
- **antientropy_grep** — regex search across article content, ripgrep-style output
- **antientropy_read** — read an article by slug with line numbers
- **antientropy_categories** — browse the full category tree

## Usage

### Remote (hosted on Fly.io)

```bash
claude mcp add --transport http antientropy https://antientropy-mcp.fly.dev/mcp
```

### Local (stdio)

```bash
claude mcp add antientropy -- uv run --directory /path/to/antientropy-mcp python -m antientropy_mcp
```

Populate the cache on first use:

```bash
uv run antientropy-sync
```

Articles are cached locally (~`~/.antientropy-mcp`). The remote server syncs daily via cron.

## Development

```bash
uv sync
uv run pytest
```

## Deploy

```bash
flyctl deploy
```

Requires a Fly.io volume named `data` mounted at `/data`. See `fly.toml` for config.
