# mcp-server-vulnwatch

Model Context Protocol (MCP) server for [VulnWatch](https://vulnwatch.tech) — a
read-mostly bridge that lets AI agents (Claude Code, Cursor, Codex, …) query
the VulnWatch **Public Developer API**.

> **VulnWatch** is a vulnerability scanning platform. This server is a thin
> client over its HTTPS API — the scanning engine and all data stay behind the
> API. No vulnerability data ever leaves the platform through this bridge.

## Features

- **Read-mostly by design.** Account quota, scan history, per-scan status and
  full JSON reports are available out of the box. Submitting a scan is a
  **side-effecting action that is disabled by default** (see [Safety](#safety)).
- **Ownership-isolated.** Every call is authenticated with *your* dashboard
  personal access token. You only ever see your own scans.
- **Offline-safe.** With no token configured the server refuses to touch the
  network and returns a clear error instead.

## Tools

| Tool | Auth | Description |
| --- | --- | --- |
| `vw_get_stats` | read | Monthly quota (used/remaining), concurrency, totals, credits |
| `vw_scan_history` | read | Paginated list of your API scans; optional `status` filter |
| `vw_scan_status` | read | Status of one scan by `check_uuid` (in_progress/completed/failed) |
| `vw_scan_report` | read | Full JSON vulnerability report for a completed scan |
| `vw_submit_scan` | **write** | Start an async scan of a URL. **Disabled unless opted in** |

## Requirements

- Python 3.10+
- A [VulnWatch](https://app.vulnwatch.tech) account with an **API token**
  (Dashboard → **API tokens**).

## Quick start

### 1. Install

```bash
# pip
pip install mcp-server-vulnwatch

# or from source
git clone https://github.com/anton-kulyk/mcp-server-vulnwatch.git
cd mcp-server-vulnwatch
pip install .
```

### 2. Configure the token

```bash
export VULNWATCH_API_TOKEN="vw_..."
```

### 3. Connect it to your client

**Claude Code:**

```bash
claude mcp add vulnwatch -- python -m vulnwatch_mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vulnwatch": {
      "command": "python",
      "args": ["-m", "vulnwatch_mcp"],
      "env": { "VULNWATCH_API_TOKEN": "vw_..." }
    }
  }
}
```

**Cursor** — Settings → MCP → Add server (command mode):

```json
{
  "command": "python",
  "args": ["-m", "vulnwatch_mcp"],
  "env": { "VULNWATCH_API_TOKEN": "vw_..." }
}
```

## Configuration

All configuration is via environment variables:

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `VULNWATCH_API_TOKEN` | **yes** | — | Your dashboard PAT |
| `VULNWATCH_API_BASE` | no | `https://app.vulnwatch.tech/api` | Override API root (self-host/staging) |
| `VULNWATCH_MCP_ALLOW_SCAN` | no | `0` | Set to `1` to enable `vw_submit_scan` |

## Safety

`vw_submit_scan` launches asynchronous scans of arbitrary URLs. To prevent a
prompt-injected agent from triggering scans without your knowledge, it is a
**confused-deputy guard**: the tool is off unless you explicitly start the
server with `VULNWATCH_MCP_ALLOW_SCAN=1`, and the token is always passed via
the environment at server start — never per-call and never read from prompts.

```bash
# opt in to scans only if you really want them
VULNWATCH_MCP_ALLOW_SCAN=1 python -m vulnwatch_mcp
```

## Development

```bash
pip install -e ".[dev]"
pytest            # offline unit + stdio transport tests
```

No API token is required to run the test suite — network is mocked and the
auth/confused-deputy gates are asserted directly.

## Example output

Real output from a live account (trimmed). `vw_get_stats`:

```json
{
  "success": true,
  "data": {
    "free_monthly_allowance": { "limit": 10, "used": 2, "remaining": 8 },
    "concurrency": { "max_in_progress": 1, "in_progress": 0 },
    "totals": { "completed": 2, "failed": 0, "in_progress": 0 },
    "credits_left": 5319
  }
}
```

`vw_scan_report` returns a full vulnerability report keyed by `score`,
`scan_highlights` (severity/source breakdown, SSL, performance),
`fingerprint` (CMS/version/theme/plugins), `cve_summary`, and
`all_findings` — a list of findings each carrying `severity`, `owasp`, `cwe`,
`cve`, `risk_score`, `recommendations` and `references`. Shape (trimmed):

```json
{
  "success": true,
  "data": {
    "score": 90,
    "scan_type_label": "Standard Scan",
    "fingerprint": { "cms": "wordpress", "cms_ver": "6.9.4" },
    "scan_highlights": {
      "issues_by_severity": { "critical": 1, "high": 33, "medium": 7, "low": 8 }
    },
    "all_findings": [
      { "title": "Webshell Detection", "severity": "critical",
        "owasp": "...", "cwe": "...", "recommendations": "..." }
    ]
  }
}
```

`vw_submit_scan` returns the new scan's uuid; poll it with `vw_scan_status`
(`progress` + per-step `scan_steps`) and fetch the finished report with
`vw_scan_report`.

## Part of the VulnWatch ecosystem

- 🏠 **Project hub & docs** — [anton-kulyk.github.io/vulnwatch-project](https://anton-kulyk.github.io/vulnwatch-project/)
- 🔌 **GitHub Action** — [anton-kulyk/vulnwatch-scan](https://github.com/anton-kulyk/vulnwatch-scan) (run scans from CI)
- 🕸️ **API gateway/proxy** — [anton-kulyk/vulnwatch-proxy](https://github.com/anton-kulyk/vulnwatch-proxy)
- 📘 **API docs** — [app.vulnwatch.tech/api/docs](https://app.vulnwatch.tech/api/docs)

## License

[MIT](./LICENSE)