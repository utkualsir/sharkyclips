# Developer tooling

## Özet (Türkçe)

- **Kuruldu (hepsi ücretsiz, hepsi kullanıcı kapsamında, repoda `.mcp.json` yok):**
  GitHub MCP sunucusu (salt okunur + lockdown), Playwright MCP (sadece yerel uygulama için,
  Edge, headless), OSV-Scanner, üç ajan (`security-auditor`, `issue-triager`,
  `product-supervisor`) `~/.claude/agents` içinde.
- **OSV-Scanner:** kurulu paketlerde açık yok. Gereksinim dosyalarının *izin verdiği* eski dolaylı
  paketler için 7 paket bulundu (pillow, pycryptodomex, httpx2, httpcore2, anyio, certifi, idna);
  alt sürüm sınırları eklendi, şimdi "No issues found". Rapor: `docs/research/osv-report.md`.
  CI'a engellemeyen "OSV-Scanner" işi eklendi. Uygulamayı etkilediği için sürüm **1.2.61**.
- **Windows Defender:** repo klasörü ve `installer/dist` tarandı: **tehdit yok**.
- **Senin yapman gereken tek şey:** GitHub MCP için bir token. Adımlar aşağıda
  ("What you still need to do by hand"). Token'ı kendin gir; hiçbir yere yazılmadı.
- GitHub'da hiçbir şey değiştirilmedi (ayar, etiket, issue, PR, yorum yok).

## What was installed

| Tool | Version | Where | Scope |
|---|---|---|---|
| GitHub MCP server | v2.1.0 (official `github/github-mcp-server`, Windows x86_64 binary, SHA-256 checked) | `%LOCALAPPDATA%\Programs\devtools\github-mcp-server\github-mcp-server.exe` | Claude Code **user** config (`~/.claude.json`, `mcpServers.github`) |
| Playwright MCP | `@playwright/mcp@0.0.84` via `npx` | npm cache; started on demand | Claude Code **user** config (`mcpServers.playwright`) |
| OSV-Scanner | v2.7.0 (official `google/osv-scanner`, SHA-256 checked) | `%LOCALAPPDATA%\Programs\devtools\osv-scanner\osv-scanner.exe` | local + CI job `osv` |
| Agents | - | `~/.claude/agents/security-auditor.md`, `issue-triager.md`, `product-supervisor.md` | Claude Code **user** scope |

No `.mcp.json`, no agent and no token is in this repo. A backup of `~/.claude.json` from before
the change is at `%LOCALAPPDATA%\Programs\devtools\claude.json.bak-before-mcp`.

### MCP server definitions (user scope)

```text
github:     github-mcp-server.exe stdio --read-only --lockdown-mode
            --toolsets=repos,issues,pull_requests,labels,actions,code_security
playwright: cmd /c npx -y @playwright/mcp@0.0.84 --browser msedge --headless --isolated
            --allowed-origins "http://127.0.0.1;http://localhost"
```

`claude mcp list` shows both as "Connected". The `claude` CLI is not on PATH on this PC; it is
the one bundled with the VS Code extension
(`%USERPROFILE%\.vscode\extensions\anthropic.claude-code-<ver>-win32-x64\resources\native-binary\claude.exe`),
or use `/mcp` inside a Claude Code chat.

## How to use

### GitHub MCP (read-only)
- 32 tools, all read-only (`github-mcp-server list-scopes --read-only --toolsets=...` shows the
  list): issues, PRs, labels, repo files/commits/releases/tags, Actions runs and job logs, code
  scanning alerts. Nothing can write: `--read-only` removes every write tool from the server.
- `--lockdown-mode` hides issue/PR/comment content from people without push access on **public**
  repos (prompt-injection filter). `utkualsir/sharkyclips` is private, so today it changes
  nothing; it starts to matter if you make the repo public. It is a content filter, not an
  authorization boundary: the token decides what can be read.
- Example: "Use the github MCP to list failing Actions runs on main and show the job log."

### Playwright MCP (local app only)
- Start the app (or the layout fixture server on port 8799), then e.g.: "Use playwright to open
  http://127.0.0.1:8000, switch to Turkish and screenshot the Updates page."
- Edge, headless, `--isolated` (fresh in-memory profile every session: no cookies or logins kept).
  `--allowed-origins` limits it to `127.0.0.1` / `localhost`; Playwright documents this as a
  guard rail, not a security boundary. It never touches the TikTok automation profile.

### OSV-Scanner
- Full report and re-run commands: `docs/research/osv-report.md`.
- Quick check: `"%LOCALAPPDATA%\Programs\devtools\osv-scanner\osv-scanner.exe" scan source -L backend/requirements.txt -L backend/requirements-dev.txt -L backend/requirements-nvidia.txt -L frontend/package-lock.json`
- CI: job "OSV-Scanner" in `.github/workflows/ci.yml` (pinned binary + SHA-256,
  `continue-on-error: true`). It runs next to the existing pip-audit / npm audit job.

### Agents (ask for them by name in Claude Code)
| Agent | Use it | Can do | Cannot do |
|---|---|---|---|
| `security-auditor` | "Run the security-auditor on my changes" before a commit/release, or after touching tokens, network fetches, CSP, updater, installers, publish code | Read, Grep, Glob; Bash only for read-only git and checks (by instruction) | edit, commit, push, print secrets |
| `issue-triager` | "Triage open issues with the issue-triager" | the read-only GitHub MCP tools listed in its file + Read/Grep/Glob. **No shell.** | post, label, close, run code. Treats all GitHub text as untrusted data |
| `product-supervisor` | "Run the product-supervisor for 1.2.x" before each release | checks VERSION, badge, CHANGELOG (simple English, max B2), 11 languages, Updates page / What's-new data, UI build version, tests | edit, commit, tag, push, release |

The security-auditor and product-supervisor have Bash, so "read-only" is an instruction for
them, not a hard limit; the issue-triager has no Bash and no GitHub write tools at all.

## Windows Defender scan (2026-11-21)

`MpCmdRun.exe -Scan -ScanType 3 -File <path> -DisableRemediation` (report only), engine
4.18.26100.4, signatures 1.463.397.0 (updated the same day):

| Path | Result | Time |
|---|---|---|
| `installer\dist` (`SharkyClips-Setup-1.2.56.exe`, `.bat`, `install.sh`) | no threats | 11 s |
| repo folder (incl. `.venv`, `node_modules`, `installer\build`) | no threats | 36 s |

## What you still need to do by hand

1. **GitHub token for the GitHub MCP server** (without it the server starts but every GitHub call
   fails with "unauthorized"):
   1. github.com -> Settings -> Developer settings -> Personal access tokens -> **Fine-grained
      tokens** -> Generate new token (free).
   2. Name `claude-mcp-readonly`, expiration 90 days, Repository access: **Only select
      repositories** -> `utkualsir/sharkyclips`.
   3. Repository permissions, all **Read-only**: Metadata, Contents, Issues, Pull requests,
      Actions, Code scanning alerts (optional). Nothing else.
   4. Put it in your **user** environment, not in a file: Start -> "Edit environment variables
      for your account" -> New -> name `GITHUB_PERSONAL_ACCESS_TOKEN`, value = the token. (Using
      the dialog keeps it out of shell history.)
   5. Fully close and reopen VS Code (MCP servers inherit the environment at start), then run
      `/mcp` in Claude Code: `github` should be connected; ask "use the github MCP to list my
      repo's releases" to test.
   - Trade-off: any program running as you can read a user environment variable. That is why the
     token is fine-grained, read-only and limited to one repo. Optional alternative without a
     stored token: register your own GitHub OAuth app and add
     `--oauth-client-id <id>` to the server args (interactive login); not done because it needs
     your account.
2. Rotate the token when it expires (same steps; just replace the variable's value).
3. Nothing else is required. The CI job is informational; make it blocking later by removing
   `continue-on-error: true` from the `osv` job once it has stayed green for a while.

## Decision log

- **No Docker on this PC** -> GitHub MCP runs as the official prebuilt binary instead of the
  Docker image. Downloaded with `gh release download` and verified against the release's
  `checksums.txt`.
- **Versions pinned to the newest release that is at least 2 weeks old** (supply-chain caution):
  github-mcp-server v2.1.0 (not 2.2.0 from 5 days ago), `@playwright/mcp` 0.0.84 (not 0.0.85 /
  0.0.86), osv-scanner v2.7.0 (not 2.7.1 from 12 days ago). The vulnerability database is live,
  so the older scanner binary does not mean older data.
- **Token via environment variable, not in `~/.claude.json`** -> the config holds no secret; the
  server reads `GITHUB_PERSONAL_ACCESS_TOKEN` from the environment it inherits. The existing `gh`
  login token was deliberately **not** reused: it has broad scopes and you asked to enter the
  token yourself.
- **Remote GitHub MCP (api.githubcopilot.com) not used**: with a token it has to be written into
  a request header in the config, which is exactly what should not happen.
- **Toolsets limited** to repos, issues, pull_requests, labels, actions, code_security (all
  read-only) instead of `all`: fewer tools, less surface.
- **Playwright MCP**: `cmd /c npx` (Windows needs the wrapper), Edge to match the repo's browser
  tests, headless, isolated profile, origins limited to localhost.
- **OSV**: scanned in two modes (exact installed set and transitive resolution of the
  requirement files). Exact: 0 findings. Transitive: 7 indirect packages could resolve to
  vulnerable old versions -> fixed with minimum-version floors (no version lowered, no package
  added that was not already installed). `requirements-nvidia.txt`: no findings.
- **Floors = app change** (the updater re-runs pip when the requirement files change, and the
  installer builds from them) -> released as **1.2.61** with a CHANGELOG entry in all 11
  languages, per CLAUDE.md rule 1. The CI job and docs alone would not have needed a bump.
- **CI**: new separate job `osv`, `continue-on-error: true`, binary pinned by version + SHA-256,
  `persist-credentials: false`, inherits the workflow's `contents: read`. The official
  `google/osv-scanner-action` was not used because it uploads SARIF and needs
  `security-events: write`.
- **Defender**: custom-path scans with `-DisableRemediation` so a hit would be reported, not
  silently quarantined. Nothing was found.
- **Agents in user scope** (`~/.claude/agents`), not `.claude/agents` in the repo, as asked.
  The issue-triager gets an explicit allowlist of read-only GitHub tools and no shell.
- **CI check after 1.2.61**: the tag run was green (OSV-Scanner job: "No issues found"). The run
  on `main` failed once in the Layout job: a 30 s timeout on `GET /api/jobs` while the fixture
  server was rendering (a timing flake, not a layout fault; the same commit passed it on the tag
  run). The 1.2.60 Backend (ubuntu) failure was a clock-dependent test (seconds before the
  YouTube quota reset at 08:00 UTC); the test was fixed in 1.2.62.
- **1.2.62 (Instagram account suspended; active again since 2026-11-26, safe settings kept)**: Instagram paused as a default target (setup kept),
  account / permission refusals are never retried by themselves, and a safe Instagram pace
  (4 h apart, max 5 rotated hashtags, no identical captions in a row). Released through the
  normal flow below.
- **Nothing changed on GitHub** besides the normal release flow of CLAUDE.md rule 1 (commit, tag,
  push, GitHub release for 1.2.61). No settings, labels, issues, PRs or comments.
