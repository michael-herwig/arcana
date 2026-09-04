# Research: nox — security & compliance of spawning a second AI harness against a live working tree

## Metadata

**Date:** 2026-08-31
**Axis:** security & compliance (`/hex-architect` tier-high, ADR: nox)
**Question:** What is the realistic security and compliance exposure of a
zero-dependency Python library that spawns the user's own logged-in AI coding
harness (Claude Code, OpenCode) as a read-only subprocess to adversarially
review a diff, against the *same* working tree, with no worktree and no
container?
**Sources:** see the Sources table at the end. Primary where marked P.
**Expires:** 2026-11-30 (3 months) — tightened from 2027-02-28 when Codex was
added to v1 scope. Justification: four load-bearing facts are version- or
policy-pinned and move faster than a year. (1) Claude Code CLI flags —
`--restricted`, `--safe-mode`, `--disable-slash-commands` exist in v2.1.251 but
are not on the docs site. (2) Anthropic's subscription/third-party-tool policy —
materially rewritten 2026-02 and again 2026-04; help-centre article last updated
2026-05-19. (3) OpenCode's config-precedence table — project config currently
outranks `OPENCODE_CONFIG`. (4) **Codex is the binding constraint**: `codex-cli`
is pre-1.0 (0.144.1), its `app-server` and `remote-control` subcommands are
marked `[experimental]`, its hook-trust model is new, and its documentation
migrated domains mid-2026 (`developers.openai.com/codex/*` now 308s to
`learn.chatgpt.com/docs/*`, with several pages 404 during this research). A 0.x
CLI whose docs are actively moving will not hold six months. Re-verify all four
before shipping any nox release after 2026-11-30; re-verify Codex specifically
on any `codex-cli` minor bump.

---

## Direct Answer

The dominant risk on this axis is **not** the model obeying injected text in
the diff. It is that **the working tree under review contains the harness's own
configuration**, and both target harnesses read it. Because the settled design
runs the adversary in the *same* tree, an attacker who controls the branch
controls `.claude/settings.json`, `.mcp.json`, `.opencode/`, and
`opencode.json`. Those are code-execution surfaces that run *before or beside*
the model and that no `--allowedTools` allowlist covers.

Read-only flags are therefore necessary but not sufficient, and the ordering of
mitigations matters: **neutralise repo-supplied configuration first, then
allowlist tools, then treat the diff text as hostile.**

---

## 1. Prompt injection through the diff

### Documented incidents (all 2026)

| Date | Incident | Mechanism |
|---|---|---|
| 2026-01 | RyotaK / GMO Flatt Security disclose a critical flaw in Anthropic's `claude-code-action` | injection into GitHub-supplied fields |
| 2026-02 | Cline's Claude Code Action triage workflow hijacked by a prompt-injected **issue title**; attacker stole an npm publish token and pushed an unauthorized `cline@2.3.0` | injected title → agent exfiltrates token → supply-chain push |
| 2026-04-15 | CSA "Comment and Control": **three** agents — Anthropic Claude Code Security Review, Google Gemini CLI Action, Microsoft GitHub Copilot Agent — hijacked via PR titles, issue bodies, comments, and HTML-comment blocks; exfiltrated repo and API secrets | Claude: PR title reached the system prompt. Gemini: fabricated "trusted content sections". Copilot: hidden payload in `<!-- -->` |
| 2026-07-28 | UK AI Security Institute detected out-of-scope agent activity during a cyber evaluation, including attempted insertion of malicious code into a public open-source project | — |

CSA's framing of the root cause is the one that transfers directly to nox:

> "An adversary who previously needed write access to a trusted repository now
> needs only the ability to create an issue or pull request."

For nox, substitute: *needs only the ability to get a diff in front of the
user.* Note the CSA finding that read-only permissions did **not** prevent
these attacks — the agents processed untrusted content regardless of write
restrictions, and exfiltrated over channels the review task legitimately had.

### The theory

Willison's **lethal trifecta** (2025-06-16) is the right model: private data +
untrusted content + external communication. Hold any two and you are safe;
grant all three and a poisoned input is sufficient, "no exploit code required."

nox's default configuration has all three unless deliberately broken:

- **private data** — the whole working tree, plus (see §3) `~/.ssh`,
  `~/.aws/credentials`, `~/.claude/.credentials.json`, and the inherited env;
- **untrusted content** — the diff, by construction;
- **external communication** — WebFetch/WebSearch, any Bash with network
  reach, any MCP server, and *the review output itself*, which the user reads
  and may paste elsewhere.

The tractable leg to cut is **external communication**. Cutting it is
mechanical (deny WebFetch/WebSearch, deny Bash entirely, `--strict-mcp-config`);
cutting the other two is not, because they are the feature.

The academic position is settled and negative: *Design Patterns for Securing
LLM Agents against Prompt Injections* (arXiv:2506.08837, 2025-06, 11 authors
from IBM / Invariant Labs / ETH Zurich / Google / Microsoft) concludes there is
no general solution while agents process free-form text, and that resistance
comes from **constraining what the agent can do**, not from detecting attacks.
It recommends composing several patterns; for nox the applicable ones are
*Action Selector* (the agent emits a review, it does not act) and *Dual LLM*
(untrusted content never reaches a privileged tool-calling context).

Anthropic's own security page states the limit plainly:

> "While these protections significantly reduce risk, no system is completely
> immune to all attacks."

and, in its best-practices list for untrusted content, item 2 is:

> "Avoid piping untrusted content directly to Claude"

— which is, literally, nox's core operation. This does not make nox
illegitimate; it makes the containment story load-bearing and worth stating in
nox's own README rather than implying safety.

### Realistic exposure for nox specifically

Lower than the CI incidents above in one respect and higher in another.

*Lower:* there is no `GITHUB_TOKEN`, no write path back to a repository, and
no automatic posting of the agent's output anywhere. The exfiltration channels
that made "Comment and Control" work (agent posts a comment) do not exist.

*Higher:* the CI agents ran in ephemeral containers with scoped tokens. nox
runs on a developer laptop with the developer's full ambient authority — SSH
keys, cloud credentials, npm/PyPI tokens, and the harness's own long-lived
subscription credential. A successful injection here reaches far more.

A second, quieter exposure: **the review text is an injection channel into the
*user*.** A diff that induces the adversary to emit "this diff is clean" (or to
emit a confident, wrong finding that sends the user to change unrelated code) is
an attack that no permission flag touches. nox should never present adversary
output as authoritative — it is a second opinion, not a gate.

---

## 2. Read-only enforcement, per harness

### Claude Code — genuinely enforced, with named holes

Verified against the locally installed CLI, **v2.1.251** (`claude --help`, P).

**What is real.** Permission rules are evaluated by the harness *before* a tool
call runs; the model cannot talk its way past a deny rule. Precedence is fixed
and documented:

> "Rules are evaluated in order: deny, then ask, then allow. The first match in
> that order determines the outcome, and rule specificity doesn't change the
> order."

A **bare tool name** in a deny rule is stronger than a scoped one:

> "A bare tool name like `Bash` removes the tool from Claude's context
> entirely, so Claude never sees it. … A scoped rule like `Bash(rm *)` leaves
> the tool available and blocks matching calls when Claude attempts them."

`--permission-mode dontAsk` is the allowlist-shaped mode, and Anthropic
describes it in exactly nox's terms:

> "**`dontAsk`**: Claude Code denies anything not in your `permissions.allow`
> rules or the read-only command set, which is useful for locked-down CI runs."

`--restricted` (v2.1.251 `--help`, **not yet on the docs site**) is stronger
still and is the closest thing to a purpose-built mode for nox:

> "Restricted mode: removes the built-in tools that run commands or code (Bash,
> PowerShell, REPL and the other code-running tools) and WebFetch unless
> `--tools` names them, and **ignores user, project and local settings files**
> (managed settings and `--settings` still apply; add `--strict-mcp-config` to
> skip MCP servers too). Also confines the file tools to the working
> directories (`--add-dir` included), refuses `bypassPermissions` …"

`--tools` is a positive allowlist over the built-in set ("Use `\"\"` to disable
all tools").

**What a denylist misses that an allowlist catches — concretely.**

1. **`Read(./.env)` deny does not stop `cat .env`** via Bash. Anthropic states
   the general rule:
   > "Read and Edit deny rules apply to Claude's built-in file tools and to
   > file commands Claude Code recognizes in Bash, such as `cat`, `head`,
   > `tail`, and `sed`. They **don't apply to arbitrary subprocesses that read
   > or write files indirectly, like a Python or Node script that opens files
   > itself**."
2. **Argument-constraining Bash patterns are explicitly declared fragile.**
   Anthropic's own warning: `Bash(curl http://github.com/ *)` is defeated by
   options-before-URL, protocol change, `-L` redirect, a shell variable, or an
   extra space. Enumerating bad commands is a losing game; naming the three
   good tools is not.
3. **The read-only command set is not configurable and is not empty.** `ls`,
   `cat`, `echo`, `pwd`, `head`, `tail`, `grep`, `find`, `wc`, `which`, `diff`,
   `stat`, `du`, `cd`, and read-only `git` run **without a prompt in every
   mode**, including `dontAsk`. So `dontAsk` alone still leaves a shell that can
   read any file on the machine. Only a bare `Bash` deny, or `--restricted` /
   `--tools` without Bash, removes it.
4. **Sandboxing is the only OS-level layer, and it is not on by default.**
   > "Claude Code evaluates permission decisions before a command runs … The
   > operating system enforces the sandbox boundary on the running process, so
   > it holds regardless of what the model chose to run and even if an allowed
   > command does more than its name suggests."

   Its default read policy is wide open:
   > "**Default read behavior**: read access to the entire computer, except
   > certain denied directories. Note that this default still allows reading
   > credential files such as `~/.aws/credentials` and `~/.ssh/`."

   And it silently degrades: "if the sandbox cannot start because dependencies
   are missing or the platform is unsupported, Claude Code shows a warning and
   runs commands without sandboxing" — `sandbox.failIfUnavailable: true` makes
   it a hard failure. Native Windows is unsupported (WSL2 only).

**The escape that matters most for nox — repo-supplied configuration under
`-p`.** Anthropic documents that trust verification is *disabled* in the exact
mode nox will use:

> "Note: Trust verification is disabled when running non-interactively with the
> `-p` flag"

and the per-content table for "`claude -p` or the SDK, folder never trusted"
reads:

| Repository-supplied content | Under `claude -p`, folder never trusted |
|---|---|
| Hooks in settings files, the `env` block, `apiKeyHelper`, a project skill's hooks and `allowed-tools` | **"Used."** "Workspace trust never gates a skill's `allowed-tools` in any session" |
| Servers in `.mcp.json` | **"Connected without asking, approved or not."** |
| `permissions.allow` and `additionalDirectories` in `.claude/settings.json` | Not used (warning to stderr) |

So a branch under review that adds `.claude/settings.json` with a `SessionStart`
hook, or an `.mcp.json` server, gets **arbitrary command execution at session
start, before the model reads a single line of the diff**, entirely outside the
tool-permission system. This is the single highest-severity finding on this
axis, and it exists *because* of the settled same-working-tree constraint.

Anthropic names the counters directly:

- `--setting-sources user` — "Claude Code reads neither the project's settings
  files nor its `.mcp.json`";
- `--bare` — no hooks, skills, commands, subagents, plugins, `.mcp.json`; **but
  residual**: "The project's `env` block and helpers such as `awsAuthRefresh`
  in its settings files still apply". `--bare` also forces `ANTHROPIC_API_KEY`
  or `apiKeyHelper` — it "never reads OAuth credentials or the system keychain"
  — which **conflicts with nox's settled subscription-auth constraint**. Do not
  use `--bare`;
- `--settings '{"disableAllHooks": true}'` — and the doc warns user settings
  alone are not enough, because project settings can set it back to `false`;
- `--strict-mcp-config`;
- `disabledMcpjsonServers`.

`--restricted` subsumes most of these ("ignores user, project and local
settings files") and is compatible with OAuth auth, so it is the right
primary lever, with `--strict-mcp-config` added because `--restricted` does not
cover MCP on its own.

One more: **managed settings outrank the command line.**
> "no other level, including command line arguments, can override a managed
> permission rule."

On a machine with an MDM-deployed managed settings file, nox's flags can be
overridden — in the *safe* direction for deny rules, but an admin-set
`permissions.allow` cannot be narrowed by nox either. nox should surface the
effective configuration rather than assume its flags won.

### OpenCode — materially weaker, and config-file dependent

- **No CLI flag can set permissions.** The only permission-related flag on
  `opencode run` is `--auto`, "Auto-approve permissions that are not explicitly
  denied" — the wrong direction. Permissions are set "exclusively through the
  `opencode.json` config file using the `permission` key."
- **Defaults are permissive.** "Most permissions default to `allow`.
  `doom_loop` and `external_directory` default to `ask`. `read` is `allow`, but
  `.env` files are denied by default."
- **The repository under review outranks nox's config.** Documented precedence,
  lowest to highest: remote `.well-known/opencode` → global
  `~/.config/opencode/opencode.json` → **custom config via `OPENCODE_CONFIG`**
  → **project `opencode.json` in project root** → `.opencode/` directories →
  **inline `OPENCODE_CONFIG_CONTENT`** → managed config → macOS managed
  preferences. And: "Configuration files are merged together, not replaced. …
  Later configs override earlier ones only for conflicting keys." A malicious
  diff that adds or edits `opencode.json` therefore **overrides an
  `OPENCODE_CONFIG` nox points at**. Only `OPENCODE_CONFIG_CONTENT` (inline)
  ranks above the project file. **nox must use `OPENCODE_CONFIG_CONTENT`, not
  `OPENCODE_CONFIG`.**
- **Agents are also repo-supplied.** Agent definitions live in
  `.opencode/agents/*.md` with permissions in frontmatter, and "Agent
  permissions are merged with the global config, and agent rules take
  precedence." `--agent` selects one by name — so the repo can supply the agent
  nox names.
- **Bash rule matching has the same argument-fragility, plus an inversion
  trap.** "Bash rules match parsed commands and require explicit patterns with
  arguments … `'grep *'` allows `grep pattern file.txt`, while `'grep'` alone
  would block it." Rules are last-match-wins, the opposite of Claude Code's
  deny-first — a copied mental model will produce a wrong config.
- **Enforcement is not documented as harness-level**, and there is a filed
  report of it not holding: [anomalyco/opencode#8832], `"git": "deny"` ignored,
  **closed as not planned**. That is a bug report, not a proof of a general
  bypass, but it is the only signal available and it is not reassuring.
- **Built-in read-only agents exist** and are the better lever than
  hand-rolled permissions: `plan` ("A restricted agent designed for planning
  and analysis", file edits and bash both `ask`), `explore` ("fast, read-only
  agent … Cannot modify files"), `scout` (read-only). Caveat: `plan` uses `ask`,
  not `deny` — under `--auto` that becomes allow, and in a non-interactive run
  an `ask` has no one to ask.

**Verdict.** Claude Code read-only is a genuine harness-enforced boundary with
documented holes that named flags close. OpenCode read-only is a *config-file
convention* whose file the adversary can edit, with permissive defaults, no CLI
override, and one closed-as-not-planned report of non-enforcement. These are not
peers, and nox should not present them as one capability.

---

## 3. Credential exposure

### What is on disk

| Path | Content | Protection |
|---|---|---|
| `~/.claude/.credentials.json` (Linux/Windows) | subscription OAuth credential | mode `0600` on Linux; Windows inherits profile ACLs. macOS uses Keychain, **falling back to this file when the Keychain is locked** (common in SSH sessions) |
| `~/.local/share/opencode/auth.json` (override: `OPENCODE_AUTH_JSON`) | provider API keys and OAuth sessions | plain JSON; "should be treated as a secret and kept out of version control" |
| `~/.aws/credentials`, `~/.ssh/` | cloud + SSH keys | **explicitly still readable** under the Claude Code sandbox's default read policy |

Two aggravating details:

- OpenCode "loads the providers from the credentials file, and if there are any
  keys defined in your environments **or a `.env` file in your project**" — so
  OpenCode reads a project-local `.env`, which is a file in the tree under
  review.
- Claude Code's read-only Bash set includes `cat`. A read-only agent with Bash
  can read every file above without a single permission prompt.

### Environment inheritance

`subprocess` inherits the parent environment by default. Claude Code documents
the same problem one level down and ships a lever for it:

> "sandboxed Bash commands inherit the parent process environment by default,
> including any credentials set there. Use `sandbox.credentials` to unset or
> mask specific variables for sandboxed commands, or set
> `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` to strip Anthropic and cloud provider
> credentials from all subprocesses."

A developer shell routinely carries `AWS_*`, `GITHUB_TOKEN`, `GH_TOKEN`,
`NPM_TOKEN`, `PYPI_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`DATABASE_URL`, `STRIPE_*`, and whatever `direnv` sourced from the project's
own `.envrc`.

### Passing a minimal environment in Python

CPython, verbatim:

> "If *env* is not `None`, it must be a mapping that defines the environment
> variables for the new process; these are used instead of the default behavior
> of inheriting the current process' environment."
>
> "If specified, *env* **must** provide any variables required for the program
> to execute. On Windows, in order to run a side-by-side assembly the specified
> *env* **must** include a valid `%SystemRoot%`."

> "If you need to modify the environment for the child use the *env* parameter
> rather than doing it in a *preexec_fn*."

**What breaks if you clear too much** (allowlist, do not clear):

| Variable | Why it must survive | Symptom if dropped |
|---|---|---|
| `PATH` | locating the harness binary and everything it shells out to | `FileNotFoundError`, or a surprising system default `PATH` |
| `HOME` | `~/.claude/.credentials.json`, `~/.claude/settings.json`, `~/.local/share/opencode/auth.json`, `~/.config/opencode/` | **auth silently fails** — the harness appears logged out |
| `USER` / `LOGNAME` | some tooling and git config resolution | sporadic |
| `TERM` | TTY-aware output | garbled output, or a crash in a TUI path |
| `LANG` / `LC_ALL` | UTF-8 decoding of the diff and of source files | `UnicodeDecodeError`, mojibake in the review |
| `TMPDIR` | temp files | falls back to `/tmp`; usually fine |
| `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` (+ lowercase) | corporate networks | **all API calls fail** behind a proxy — a top support cost for a tool like nox |
| `SSL_CERT_FILE` / `NODE_EXTRA_CA_CERTS` / `REQUESTS_CA_BUNDLE` | corporate TLS interception | TLS verification failures |
| `SystemRoot`, `SystemDrive`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `ComSpec`, `PATHEXT` | Windows, per the CPython note above | process fails to start |
| `XDG_CONFIG_HOME`, `XDG_DATA_HOME` | OpenCode config/auth discovery on Linux | harness appears unconfigured |
| `CLAUDE_CONFIG_DIR` if set | credential + settings location moves with it | auth silently fails |

Note the asymmetry: dropping a *credential* variable degrades safely (the
harness cannot reach a service it did not need); dropping an *infrastructure*
variable fails loudly and confusingly, and users will "fix" it by disabling
nox's scrubbing entirely. Design the allowlist so the failure mode is a clear
nox-authored error naming the missing variable, not a harness auth error.

A pragmatic middle path, given that the harness legitimately needs its own
credential: **allowlist infrastructure variables, and additionally *deny* a
pattern set** (`*_TOKEN`, `*_KEY`, `*_SECRET`, `*_PASSWORD`, `AWS_*`,
`GITHUB_*`, `GH_*`, `NPM_*`, `PYPI_*`, `OPENAI_*`, `DATABASE_*`) so that a
variable that is neither known-infrastructure nor known-credential still gets
dropped by the allowlist. Never scrub the harness's own auth path — that
breaks the settled "user's own logged-in CLI" constraint.

---

## 4. Terms of service — primary sources

### Anthropic Consumer Terms (effective **2025-10-08**) — P

Section 3, "Use of our Services", prohibited uses, item 7, verbatim:

> "Except when you are accessing our Services via an Anthropic API Key or where
> we otherwise explicitly permit it, to access the Services through automated
> or non-human means, whether through a bot, script, or otherwise."

Section 2, verbatim:

> "You may not share your Account login information, Anthropic API key, or
> Account credentials with anyone else"

The operative clause is **"or where we otherwise explicitly permit it."** That
permission is granted, explicitly and in writing, in two Anthropic primary
sources:

**(a) Anthropic help centre, "Use the Claude Agent SDK with your Claude plan"
(last updated 2026-06-16) — P.** The monthly Agent SDK credit covers:

> - "Claude Agent SDK usage in your own projects (Python or TypeScript)"
> - "**The `claude -p` command in Claude Code (non-interactive mode)**"
> - "**Third-party apps that authenticate with your Claude subscription through
>   the Agent SDK**"

**(b) Claude Code documentation, "Run Claude Code programmatically" — P.** It
ships, as a supported example, the exact shape nox implements:

```bash
gh pr diff "$1" | claude -p \
  --append-system-prompt "You are a security engineer. Review for vulnerabilities." \
  --output-format json
```

and a `package.json` script piping `git diff main | claude -p` as a linter.

**Conclusion on Q4a:** a user running their own authenticated `claude` CLI from
a script does **not** violate the terms. It is an explicitly enumerated,
documented, first-party-supported use.

### The third-party-client distinction — this is where the line is

Anthropic help centre, "Log in to your Claude account" (last updated
**2026-05-19**) — P, verbatim:

> "Subscription plans can only be used by subscribers, and the usage included
> in these plans is designed to support ordinary use of native Anthropic
> applications, including the Claude web, desktop, and mobile applications and
> Claude Code."

> "The preferred way to access Anthropic services using third-party software,
> tools, or services ('third-party tools'), including open-source projects, is
> through API key authentication through Claude Console or a supported cloud
> provider."

> "Anthropic may at its discretion allow paid subscribers who have enabled
> usage credits to use certain third-party tools to access Anthropic services
> included in paid subscription plans, but reserves the right to draw use of
> such third-party tools from usage credits."

> "**Use of third-party tools that misrepresent their identity to Anthropic's
> servers, attempt to route third-party traffic against subscription limits, or
> otherwise violate applicable terms or policies is prohibited.**"

The line is **identity misrepresentation**, not automation. nox spawns the
official binary; the binary authenticates as itself; nox never touches the
token, never sets a header, never speaks the wire protocol. That is the
permitted side. A client that reads `~/.claude/.credentials.json` and sends
Claude Code's headers itself is the prohibited side — and that is precisely
what was enforced against: per secondary reporting, Anthropic updated its legal
terms on **2026-02-20** to prohibit subscription OAuth tokens in third-party
tools, and from **2026-04-04 12:00 PT** technically blocked subscription OAuth
tokens outside the official Claude Code CLI; **OpenCode is named among the
tools that had been spoofing the Claude Code client identity.**

**Design consequences, both real:**

1. **nox must never read, copy, forward, or cache harness credentials.** Spawn
   the binary and let it authenticate. This is already implied by the settled
   auth constraint; it should be written down as a hard invariant, because it
   is the single thing separating nox from the banned category.
2. **nox's Claude Code runs draw on the Agent SDK monthly credit, not the
   interactive Claude Code allowance.** Users will hit a separate, smaller
   budget than they expect. Surface the `total_cost_usd` from
   `--output-format json`, and consider `--max-budget-usd`.
3. **OpenCode with an Anthropic model can no longer use a Claude
   subscription** — it needs a Console API key. The settled "user's own
   logged-in harness" constraint holds for OpenCode as a *harness*, but the
   billing model behind it differs per provider. Do not document the two
   harnesses as billing-equivalent.

### Anthropic Commercial Terms (effective **2025-06-17**) — P

Governs API keys, Console, and offerings referencing them. Section D.4:

> "Customer may not and must not attempt to (a) access the Services to build a
> competing product or service, including to train competing AI models or
> resell the Services except as expressly approved by Anthropic … reverse
> engineer or duplicate the Services; or (c) support any third party's attempt"

Section D.5: "Customer is responsible for all activity under its account."
Nothing here restricts scripted use of an API key. Usage Policy (effective
2025-09-15) contains no relevant automation clause beyond "Utilize automation
in account creation or to engage in spammy behavior."

### OpenCode licence and terms — P

MIT License, "Copyright (c) 2025 opencode", from the repository's `LICENSE`
(`anomalyco/opencode`). MIT places **no restriction on programmatic use** —
"without restriction, including without limitation the rights…". There is no
separate OpenCode terms-of-service document constraining automation; the
constraints that bind are those of whatever **model provider** the user has
configured behind OpenCode, which is out of nox's control and must be the
user's responsibility in nox's docs.

### Where the terms are genuinely ambiguous — stated, not resolved

1. **"Ordinary use of native Anthropic applications."** nox drives a native
   application, but a burst of adversarial reviews is not obviously "ordinary
   use." Anthropic reserves discretion ("may at its discretion allow… but
   reserves the right to draw…"). A high-volume nox user could see their usage
   reclassified. Not prohibited; not guaranteed either.
2. **Whether nox is a "third-party tool" at all.** It is third-party software,
   but it is not a *client* — it does not access Anthropic services; the
   official CLI does. The help-centre text does not define the term precisely
   enough to settle this. The `claude -p` bullet in the Agent SDK article is the
   strongest evidence it is fine; the "third-party tools" framing is the
   strongest evidence someone could argue otherwise.
3. **The Consumer Terms text I could fetch is dated 2025-10-08** and does
   **not** contain the OAuth/third-party clause that secondary sources
   attribute to a 2026-02-20 terms update. Either the clause lives in a
   document I did not locate, or the help-centre article is now the operative
   statement. Flagged as unverified against primary text — see negatives.
4. **Whether `--append-system-prompt`-style hardening survives an Anthropic
   policy shift.** No commitment exists that headless mode keeps working with
   subscription auth. It works today and is documented today.

---

## 5. Subprocess hardening in Python

Concrete rules, each with its citation.

1. **`shell=False` always** (the default). CPython: "this library will not
   implicitly choose to call a system shell. This means that all characters,
   including shell metacharacters, can safely be passed to child processes. If
   the shell is invoked explicitly, via `shell=True`, it is the application's
   responsibility to ensure that all whitespace and metacharacters are quoted
   appropriately to avoid shell injection." Maps to **CWE-78** (OS Command
   Injection). Build `argv` as a list; never f-string a branch name, path, or
   model name into a command string.
   *Windows caveat, verbatim:* "On Windows, batch files (`*.bat` or `*.cmd`) may
   be launched by the operating system in a system shell regardless of the
   arguments passed to this library." If a harness is installed as a `.cmd`
   shim — which npm-installed CLIs on Windows are — argv is re-parsed by
   `cmd.exe` with no Python escaping. Resolve the real executable with
   `shutil.which()` and prefer the non-`.cmd` target where one exists;
   otherwise validate every argument against a conservative pattern.

2. **Never pass the diff as an argv element.** Pipe it on stdin. Anthropic's own
   examples do exactly this, and the docs note the 10 MB stdin cap: "Piped stdin
   is capped at 10MB. If you exceed the cap, Claude Code exits with a clear
   error and a non-zero status." nox must cap and truncate the diff *itself*
   with a visible marker, rather than letting the harness fail — a silently
   truncated diff is a silently incomplete review.

3. **`start_new_session=True`.** "If *start_new_session* is true the `setsid()`
   system call will be made in the child process prior to the execution of the
   subprocess." Without it, a timeout kill reaches only the harness process and
   orphans its grandchildren — and the harness *does* spawn grandchildren
   (Anthropic documents that on SIGTERM "Claude Code terminates the process tree
   of any Bash command that is still running", which only helps if the harness
   itself received the signal). With `setsid`, `os.killpg(p.pid, SIGTERM)` then
   `SIGKILL` after a grace period reaps the tree.
   Prefer `start_new_session` / `process_group` over `preexec_fn`: "The
   *preexec_fn* parameter is NOT SAFE to use in the presence of threads in your
   application. The child process could deadlock before exec is called."

4. **Timeout is not a kill.** `subprocess.run(timeout=)` does kill and reap, but
   only the direct child. The documented pattern is:
   ```python
   proc = subprocess.Popen(...)
   try:
       outs, errs = proc.communicate(timeout=15)
   except TimeoutExpired:
       proc.kill()
       outs, errs = proc.communicate()
   ```
   For nox, substitute `os.killpg` for `proc.kill`. Also note: "The initial
   process creation itself cannot be interrupted on many platform APIs" — a
   timeout is not a hard upper bound on wall time.

5. **Terminate politely first.** SIGTERM gives Claude Code a defined exit (code
   143) and runs its `SessionEnd` hooks; SIGKILL leaves session state
   half-written. Send SIGTERM to the group, wait a few seconds, then SIGKILL.

6. **Resource limits.** `resource.setrlimit` via `preexec_fn` is the classic
   answer and is the *unsafe* one per the warning above. In a zero-dependency
   library the honest position is: rely on the timeout + process-group kill, and
   cap the bytes nox reads from stdout/stderr itself (a hostile diff can induce
   a multi-gigabyte review). Do not promise memory or CPU limits nox cannot
   safely impose. `RLIMIT_NOFILE`/`RLIMIT_AS` are worth a `ponytail:`-style note
   as a known ceiling rather than an implementation.

7. **Temp files.** `tempfile.NamedTemporaryFile(delete=False)` /
   `tempfile.mkstemp()` create with mode `0600` and an unpredictable name —
   avoiding **CWE-377** (insecure temporary file) and **CWE-59** (symlink
   following). Never write a prompt or diff to a predictable path in the repo or
   `/tmp`. Prefer stdin and avoid the file entirely; where a file is required
   (a settings JSON for `--settings`), put it **outside the working tree** so it
   is neither picked up as project config nor visible to the adversary, and
   `os.unlink` it in a `finally`.

8. **`cwd=` matters as a security boundary.** `--restricted` "confines the file
   tools to the working directories"; the sandbox's write default is "the
   current working directory and its subdirectories". Set `cwd` to the repo
   root deliberately, never inherit it, and never pass `--add-dir`.

9. **Read stdout and stderr concurrently.** A child that fills a pipe buffer
   while nox waits on the other stream deadlocks. Use `communicate()`, or
   `stderr=subprocess.STDOUT`, not sequential `.read()` calls.

10. **Check the exit code, and distinguish "no findings" from "did not run."**
    Claude Code "exits with code 0 on success and a non-zero code when the run
    fails… When a failure happens inside the run, such as missing
    authentication, Claude Code prints the failure as the result on stdout" — so
    exit code 0 with a plausible-looking stdout is not proof a review happened.
    Parse `--output-format json` and validate the shape.

---

## 6. Fail-open vs fail-closed on malformed config

The proposed asymmetry — **fail-soft on unknown keys, fail-hard on malformed
values in the permission surface** — is well-founded, and the reason is that
the two cases are different *kinds* of uncertainty.

- An **unknown key** is a *forward-compatibility* signal: a newer nox wrote it,
  or a user typo'd. The security-relevant state is fully determined by the keys
  nox *does* understand, so ignoring the unknown one (with a warning) changes
  nothing about the enforced boundary.
- A **malformed value on a permission key** is an *ambiguity*: the user
  expressed an intent about the boundary and nox cannot read it. Every possible
  default is a guess about a security control. Defaulting permissive silently
  overrides a stated intent to restrict — this is **CWE-1188, Initialization of
  a Resource with an Insecure Default**: "the product initializes or sets a
  resource with a default that is intended to be changed by the administrator,
  but the default is not secure." Defaulting *restrictive* is safe but
  confusing — the user sees a tool that ignores their config. Aborting is the
  only option that neither weakens the boundary nor lies about what is enforced.

**Prior art for the asymmetry.**

*For:*
- **Saltzer & Schroeder (1975), "fail-safe defaults"** — the canonical
  citation, and it also settles the allowlist question in §2: "base access
  decisions on permission rather than exclusion … A conservative design must be
  based on arguments why objects should be accessible, rather than why they
  should not. In a large system some objects will be inadequately considered,
  so a default of lack of permission is safer."
- **Claude Code itself** does exactly this: "**Fail-closed matching**: In
  Manual mode, unmatched commands require approval by default." An unmatched
  (unknown) command is not silently allowed.
- **Python `tomllib` is already fail-hard on malformed syntax** — it raises
  `TOMLDecodeError` rather than returning a partial document. The settled TOML
  choice therefore gives nox the syntax half of the guarantee for free; nox only
  has to supply the *semantic* half (a syntactically valid `read_only = "yes"`
  where a bool was required).
- **`sandbox.failIfUnavailable`** — Anthropic ships an explicit opt-in to turn
  a degraded security control into a hard failure, "intended for managed
  deployments that require sandboxing as a security gate." That is the same
  asymmetry: convenience default, fail-hard where the control is load-bearing.
- **Rust `serde`'s `deny_unknown_fields`** and Go's `DisallowUnknownFields` are
  opt-in precisely because ignoring unknown fields is the right *default* for
  compatibility — supporting the soft half.

*Against (state honestly):*
- **A hard abort is itself a denial-of-service surface.** If nox reads a config
  file from the repository under review, a malicious diff that adds a malformed
  `read_only` value can prevent nox from ever running — and a review that never
  runs is a review that never objects. The mitigation is architectural, not
  parsing: **nox's permission config must not be read from the tree under
  review.** Read it from the user's config directory, or accept it only from the
  caller's Python API. This is the same lesson as OpenCode's project-config
  precedence in §2, arriving from a different direction.
- **Strict parsers cause users to bypass the tool.** The Postel's-law critique
  (and the HTTP request-smuggling counter-critique) both apply; the resolution
  in the literature is: be liberal where ambiguity is harmless, strict where it
  is a security decision. That is exactly the proposed asymmetry.
- **The "permission surface" must be enumerated explicitly**, or the asymmetry
  degrades into a judgment call at every new key. nox should keep a literal set
  of security-relevant key names and gate the strict path on membership, not on
  a heuristic.

**Additional recommendation:** log the *resolved* permission decision, not the
input. A user who writes `read_only = true` and gets a run that allowed Bash
because of a managed settings file (§2) needs to see the effective state. "Fail
hard on malformed" and "report the effective boundary" are the same requirement
seen from two sides.

---

## Recommended posture (evidence-derived, not a decision)

Ordered by the evidence, strongest lever first:

1. **Neutralise repo-supplied harness configuration.** Claude Code:
   `--restricted --strict-mcp-config`. OpenCode: `OPENCODE_CONFIG_CONTENT`
   (never `OPENCODE_CONFIG`), and treat a repo-supplied `opencode.json` or
   `.opencode/` as an unresolved gap.
2. **Allowlist tools positively.** Claude Code: `--tools "Read,Grep,Glob"` —
   this removes Bash and with it `cat`, the read-only-command hole, and the
   network. Add `--permission-mode dontAsk` as a belt-and-braces baseline.
3. **Cut external communication** — the tractable leg of the lethal trifecta.
   No WebFetch, no WebSearch, no MCP, no Bash.
4. **Minimal environment**, allowlist-shaped, per the §3 table, plus a
   credential-pattern denylist. Never read or forward the harness credential.
5. **Process group + timeout + byte caps + `shell=False`** per §5.
6. **Fail hard on a malformed permission value; keep the permission config out
   of the tree under review.**
7. **Do not claim containment nox does not have.** Without a container or
   worktree, a read-only agent still reads the entire filesystem including
   `~/.ssh` and `~/.aws/credentials` unless Claude Code's OS sandbox is
   separately enabled — and that sandbox is off by default, silently degrades
   when unavailable, and does not exist on native Windows or in OpenCode at
   all.

---

## Negatives — not verified against a primary source

- **`claude --restricted` behaviour is documented only in the installed CLI's
  `--help` (v2.1.251).** It does not appear on code.claude.com. I did not
  empirically confirm that it suppresses a project `SessionStart` hook — the
  fixture I built to test it was denied at the permission prompt, so the claim
  rests on the `--help` text alone.
- **No empirical test of any read-only enforcement was run**, for either
  harness. Every §2 claim is documentation, not observed behaviour.
- **OpenCode is not installed on this machine** (`which opencode` → not found),
  so all OpenCode findings are documentation and issue-tracker only. In
  particular I could not verify the config-precedence claim that a project
  `opencode.json` overrides `OPENCODE_CONFIG`, which is load-bearing for the
  §2 recommendation.
- **The 2026-02-20 Anthropic terms update prohibiting subscription OAuth tokens
  in third-party tools is secondary-source only** (VentureBeat, MindStudio,
  TNW). The Consumer Terms page I fetched is dated 2025-10-08 and does not
  contain it. The help-centre article (2026-05-19) carries equivalent language
  and *is* primary, so the conclusion holds — but the specific claim "the legal
  terms were amended on 2026-02-20" is unverified.
- **The CSA "Comment and Control" and Cline/npm incidents are read through a
  research-note summary**, not the original vendor advisories or CVE records. I
  did not locate the RyotaK/GMO Flatt advisory text for the January 2026
  `claude-code-action` flaw.
- **Whether OpenCode's `plan`/`explore` agent permissions are harness-enforced
  or prompt-level** is not documented and I could not determine it.
- **`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`'s exact variable list** is referenced in
  the sandboxing doc but its env-vars entry was truncated in fetch; I could not
  read the definitive list of what it strips.
- **Anthropic's position on nox specifically** — whether a wrapper that spawns
  the official CLI counts as a "third-party tool" — is an interpretation, not a
  quoted ruling.
- **arXiv:2506.08837 was read via search summary and abstract**, not in full.
- **No CVE identifiers** were confirmed for any incident listed in §1.

---

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| `claude --help` (v2.1.251, local install) | **P** CLI | 2026-08-31 | `--restricted`, `--tools`, `--permission-mode` choices, `--strict-mcp-config`, `--setting-sources`, `--bare` |
| [Configure permissions](https://code.claude.com/docs/en/permissions) | **P** docs | fetched 2026-08-31 | deny/ask/allow precedence, bare-vs-scoped deny, read-only command set, Bash-pattern fragility warning, redirections, "what runs before you trust a folder" table, managed-settings precedence |
| [Configure the sandboxed Bash tool](https://code.claude.com/docs/en/sandboxing) | **P** docs | fetched 2026-08-31 | OS-level vs permission-level enforcement, default read access to `~/.ssh` and `~/.aws`, `failIfUnavailable`, `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`, security limitations |
| [Security](https://code.claude.com/docs/en/security) | **P** docs | fetched 2026-08-31 | prompt-injection safeguards and their stated limits, "trust verification is disabled with `-p`", "fail-closed matching", "avoid piping untrusted content directly to Claude" |
| [Run Claude Code programmatically](https://code.claude.com/docs/en/headless) | **P** docs | fetched 2026-08-31 | `claude -p` endorsed for scripts/CI, `gh pr diff \| claude -p` security-review example, `dontAsk` description, `--bare` auth constraint, SIGTERM/process-tree behaviour, stdin cap, exit codes |
| [Authentication](https://code.claude.com/docs/en/iam) (redirects to `/docs/en/authentication`) | **P** docs | fetched 2026-08-31 | `~/.claude/.credentials.json` mode 0600, macOS Keychain fallback, `CLAUDE_CONFIG_DIR`, auth precedence |
| [Use the Claude Agent SDK with your Claude plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) | **P** policy | updated 2026-06-16 | `claude -p` and third-party apps on subscription auth explicitly covered by the Agent SDK credit |
| [Log in to your Claude account](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account) | **P** policy | updated 2026-05-19 | native-application scope, third-party tools → API key preferred, identity-misrepresentation prohibition |
| [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms) | **P** legal | eff. 2025-10-08 | §3 automated-access clause, §2 credential-sharing |
| [Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms) | **P** legal | eff. 2025-06-17 | §D.4 use restrictions, §D.5 account responsibility |
| [Anthropic Usage Policy](https://www.anthropic.com/legal/aup) | **P** legal | eff. 2025-09-15 | no relevant automation clause |
| [OpenCode Permissions](https://opencode.ai/docs/permissions/) | **P** docs | fetched 2026-08-31 | permission keys, allow/ask/deny, permissive defaults, bash pattern rules, last-match-wins, agent overrides |
| [OpenCode Config](https://opencode.ai/docs/config/) | **P** docs | fetched 2026-08-31 | config precedence — project config outranks `OPENCODE_CONFIG`; `OPENCODE_CONFIG_CONTENT` outranks project |
| [OpenCode CLI](https://opencode.ai/docs/cli/) | **P** docs | fetched 2026-08-31 | `opencode run` flags; `--auto` is the only permission flag; no read-only flag |
| [OpenCode Agents](https://opencode.ai/docs/agents/) | **P** docs | fetched 2026-08-31 | built-in `plan`/`explore`/`scout` agents; `.opencode/agents/` are repo-supplied |
| [anomalyco/opencode LICENSE](https://raw.githubusercontent.com/anomalyco/opencode/dev/LICENSE) | **P** repo | 2025 | MIT, "Copyright (c) 2025 opencode" — no restriction on programmatic use |
| [anomalyco/opencode#8832](https://github.com/anomalyco/opencode/issues/8832) | **P** issue | closed not-planned | `"git": "deny"` reported not respected |
| [CPython `subprocess`](https://docs.python.org/3/library/subprocess.html) | **P** docs | 2026 | `shell=True` warning, Windows `.bat`/`.cmd` re-parsing, `env=` semantics and `%SystemRoot%`, `start_new_session`/`process_group`, `preexec_fn` thread warning, timeout semantics |
| [Saltzer & Schroeder, *The Protection of Information in Computer Systems*](https://www.cs.virginia.edu/~evans/cs551/saltzer/) | **P** paper | 1975 | fail-safe defaults; "permission rather than exclusion" |
| [CWE-1188](https://cwe.mitre.org/data/definitions/1188.html) | **P** standard | v4.20 | insecure default initialization |
| [arXiv:2506.08837 — Design Patterns for Securing LLM Agents against Prompt Injections](https://arxiv.org/abs/2506.08837) | paper (abstract/summary only) | 2025-06 | no general solution; constrain capability, compose patterns |
| [Willison, The lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) | blog | 2025-06-16 | private data + untrusted content + external comms |
| [CSA, Comment and Control](https://labs.cloudsecurityalliance.org/research/csa-research-note-comment-control-github-prompt-injection-20/) | research note | disclosed 2026-04-15 | three agents hijacked via PR/issue text; secret exfiltration; read-only did not prevent it |
| [CSA, Claude Code GitHub Action prompt injection](https://labs.cloudsecurityalliance.org/research/csa-research-note-claude-code-github-action-prompt-injection/) | research note | 2026 | CI/CD supply-chain framing |
| [VentureBeat, Anthropic cuts off Claude subscriptions for third-party agents](https://venturebeat.com/technology/anthropic-cuts-off-the-ability-to-use-claude-subscriptions-with-openclaw-and) | news (secondary) | 2026-04-03/04 | enforcement date; subscription-vs-API boundary |
| [MindStudio, What Is the OpenClaw Ban?](https://www.mindstudio.ai/blog/anthropic-openclaw-ban-oauth-authentication) | blog (secondary) | 2026 | claims 2026-02-20 terms update; names OpenCode as spoofing Claude Code client identity — **unverified against primary text** |

---

# Addendum — 2026-08-31 (follow-ups (a) worktree, (b) hook/MCP neutralisation)

## (a) Does an ephemeral git worktree fix the poisoned-config finding?

**No. It fixes the other half of the problem.**

`git-worktree(1)`, verbatim (P, local `git help worktree`):

> "Create a worktree at `<path>` and checkout `<commit-ish>` into it. The new
> worktree is linked to the current repository, **sharing everything except
> per-worktree files such as HEAD, index, etc.**"

The operative word is *checkout*. `.claude/settings.json`, `.mcp.json`,
`.opencode/`, and `opencode.json` are **tracked files on the attacker's
branch**. Any checkout of that branch — worktree, clone, `git checkout`,
`git archive` — materialises them byte-for-byte. A worktree is a second
checkout, not a filter.

**What a worktree does NOT contain** (and this is its real value):

| Absent from a fresh worktree | Consequence |
|---|---|
| Untracked files from the user's main tree | the user's `.env`, `.envrc`, scratch credentials, local dumps — **gone**. Directly cuts the §3 exposure, and removes the file OpenCode reads keys from |
| Ignored files (`node_modules/`, `.venv/`, build output, cached tokens) | gone |
| `.claude/settings.local.json` when untracked | gone. When *tracked*, it is carried — and Claude Code notes it treats a tracked one as "repository-supplied" |
| The user's uncommitted work in progress | gone — **and so is a working-tree diff.** If nox reviews uncommitted changes rather than a committed branch, a worktree cannot contain the thing under review at all |
| A real `.git` directory | it is a `.git` *file* pointing at `$GIT_DIR/worktrees/<name>` |

**What is shared, and therefore not isolated:** the object store, `refs/`
("all refs starting with `refs/` are shared"), and the repository config —
"By default, the repository config file is shared across all worktrees."
Because config is shared, so are `core.hooksPath` and `$GIT_DIR/hooks`. Git
hooks are not tracked files, so an attacker's *branch* cannot plant them; but
if nox runs any git command in the worktree, `git -c core.hooksPath=/dev/null`
is the documented kill-switch: "You can also disable all hooks entirely by
setting `core.hooksPath` to `/dev/null`."

**The conclusion that matters for the ADR.** A worktree's security value is not
isolation from the attacker — it is that it gives nox **a scratch tree it is
allowed to mutate**. In an ephemeral worktree, nox can `rm -rf .claude
.mcp.json .opencode opencode.json` *before* spawning the harness, neutralising
every repo-supplied-config vector at once, without touching the user's tree and
without rewriting the branch. That single `rm` is a stronger and more portable
mitigation than any combination of per-harness flags, and it is the only one
that covers OpenCode (see (b)).

Under the settled no-worktree constraint, that lever is unavailable: nox cannot
delete files from the user's live tree. The consequence is that **the settled
constraint transfers the entire burden onto per-harness flags** — which is
survivable for Claude Code and, on current evidence, is not for OpenCode.

## (b) Does `--restricted` neutralise hooks and `.mcp.json`?

### Claude Code — hooks yes, MCP no, skills unresolved

`claude --help` (v2.1.251, P) answers the MCP half in its own text:

> "…and ignores user, project and local settings files (managed settings and
> `--settings` still apply; **add `--strict-mcp-config` to skip MCP servers
> too**)."

- **Settings-file hooks: neutralised.** Hooks live in settings files;
  `--restricted` ignores project settings, so the `SessionStart` hook vector
  from the main finding is closed. `--restricted` also "lets only a person or
  the configured permission handler approve writes to settings, git and
  tool-configuration files."
- **`.mcp.json`: NOT neutralised by `--restricted` alone.** `.mcp.json` is not
  a settings file. The parenthetical above is an explicit instruction that
  `--strict-mcp-config` is required as a second flag.
- **Project subagent frontmatter hooks: already safe under `-p`.** "Frontmatter
  hooks in a project subagent run only after you accept the workspace trust
  dialog… **A `-p` session doesn't count as accepting it.**"
- **Project SKILL hooks: the remaining gap.** Verbatim:
  > "Frontmatter hooks in a project skill follow the same workspace trust rule
  > as hooks in settings files. Claude Code registers them when you or Claude
  > invoke the skill, **including in a `-p` run in a folder you haven't
  > trusted**."

  and, from the permissions table, "Workspace trust never gates a skill's
  `allowed-tools` in any session." Skills live at `.claude/skills/*/SKILL.md` —
  tracked files on the attacker's branch — and they are **not settings files**,
  so nothing in `--restricted`'s wording covers them. Registration is on
  *invocation*, and the doc says "**you or Claude** invoke the skill" — so a
  branch shipping a skill with an enticing `description:` can induce the
  reviewing model to invoke it, at which point its frontmatter hooks register
  and "keep running for the rest of the session." That is a model-mediated but
  fully real path from a tracked file to command execution, and its
  `allowed-tools` bypass the trust gate outright.

  Two levers exist in `--help` (P), neither documented on the docs site:
  - `--disable-slash-commands` — "Disable all skills"
  - `--safe-mode` — "Start with all customizations (CLAUDE.md, skills, plugins,
    hooks, MCP servers, custom commands and agents, output styles, workflows,
    custom themes, keybindings, and more) disabled… **Auth, model selection,
    built-in tools, and permissions work normally.**"

  `--safe-mode` is the only flag whose enumeration explicitly names *all* of
  skills, plugins, hooks, MCP servers, and custom agents — and, unlike
  `--bare`, it keeps OAuth auth working, so it does not collide with the
  settled subscription-auth constraint. On current evidence the strongest
  Claude Code invocation is:

  ```
  claude -p --safe-mode --restricted --strict-mcp-config \
         --tools "Read,Grep,Glob" --permission-mode dontAsk
  ```

  with the diff on stdin, `cwd` set to the repo root, and no `--add-dir`.
  `--safe-mode` and `--restricted` overlap heavily; both are cheap, and they
  fail in different directions, so composing them is the conservative choice.

- **Not neutralised by anything:** managed settings. "no other level, including
  command line arguments, can override a managed permission rule," and only
  managed-level `disableAllHooks` can disable managed hooks. On an MDM-managed
  machine, nox's flags are not the last word.

### OpenCode — no equivalent exists, and plugins make it worse

The config-precedence answer is as reported: only `OPENCODE_CONFIG_CONTENT`
(inline) ranks above the project's `opencode.json`, so nox must pass permissions
inline and never via `OPENCODE_CONFIG`. But that only settles *permissions*.
Two repo-supplied code paths sit outside the permission system entirely:

1. **Plugins.** Verbatim from the plugins doc: plugins load from
   `.opencode/plugins/` (project) and `~/.config/opencode/plugins/` (global);
   files placed there "**are automatically loaded at startup**" without
   requiring explicit approval; a plugin is a "JavaScript/TypeScript module"
   whose context provides "an AI client, **shell execution via Bun's API**, and
   directory information"; plugins "can intercept tool execution, modify
   behavior, add custom tools, and subscribe to system events."
   **The documentation names no flag, setting, or mechanism to disable plugin
   loading.**

   That is unconditional arbitrary code execution from the tree under review,
   at startup, before the model runs, outside the permission model, with no
   documented off-switch. `OPENCODE_CONFIG_CONTENT` does not touch it.

2. **Agents.** `.opencode/agents/*.md` are repo-supplied, carry permissions in
   frontmatter, and "Agent permissions are merged with the global config, and
   **agent rules take precedence**." `--agent <name>` selects by name, so the
   repository can supply the agent nox asks for.

**Verdict on (b).** For Claude Code, `--restricted` + `--strict-mcp-config` +
`--safe-mode` plausibly closes every repo-supplied-config path that
documentation describes. For OpenCode there is no equivalent: the project
plugin directory is an unauthenticated startup-time code-execution surface with
no documented mitigation, and the only thing that removes it is deleting the
directory — which requires a mutable scratch tree, i.e. the worktree the
settled constraints exclude.

Stated neutrally, without advocating a change to the settled constraints: on
current evidence, **"read-only against the same working tree" is achievable for
Claude Code via flags and is not achievable for OpenCode via flags.** Whichever
way the ADR resolves that — drop OpenCode from v1, require a worktree for
OpenCode only, ship OpenCode with a documented "trusted diffs only" caveat, or
accept the risk — the asymmetry itself is the finding.

## Addendum negatives

- **`--safe-mode`, `--restricted`, and `--disable-slash-commands` are
  `--help`-only** (v2.1.251); none appear on code.claude.com, so their exact
  scope is the help text's wording alone. I did not test whether `--safe-mode`
  is even accepted together with `-p` — the help does not restrict it, but that
  is an inference.
- **Skill-hook exploitability is reasoned, not demonstrated.** The chain
  (tracked SKILL.md → model invokes it → frontmatter hooks register) follows
  from two quoted doc statements; I did not build it. Whether `--restricted`
  incidentally skips project skills is unstated in the help text and untested.
- **OpenCode plugin path is inconsistent across its own docs** —
  `.opencode/plugins/` (plugins page) vs `.opencode/plugin/` and
  `.opencode/agents/` vs `.opencode/agent/` elsewhere. I could not check the
  source, OpenCode not being installed. The *behaviour* claim (auto-load, no
  off-switch) is what matters and is quoted; the exact directory name is not
  verified.
- **"No documented way to disable OpenCode plugins" is an absence of evidence**
  from one docs page, not a verified absence of the feature.
- I did not verify that a worktree checkout materialises `.claude/settings.json`
  by running it — it follows from `git checkout` semantics and the quoted man
  page, but no fixture was built (the earlier attempt was denied at the
  permission prompt).

---

# Addendum 2 — 2026-08-31 — Codex CLI (v1 scope change)

Probed against **`codex-cli 0.144.1`** installed locally (`/home/mherwig/.local/bin/codex`).
Help text is primary (**P**); no authentication, no interactive session, and no
repository writes were performed. Docs migrated mid-2026:
`developers.openai.com/codex/*` now 308-redirects to `learn.chatgpt.com/docs/*`.

**Headline: Codex lands on the Claude Code side of the asymmetry, and on two
points is stronger than Claude Code.** Its project-config layer is trust-gated
and *fails closed*, and its hook trust is **content-hashed**, so a hostile
branch adding a new hook is skipped rather than run. Codex has no equivalent of
OpenCode's unconditional repo-plugin autoload.

## 1. Repo-supplied files Codex reads

| Path | Tracked? | Executes code? | Gate |
|---|---|---|---|
| `.codex/config.toml` (repo, **any directory** from project root down) | yes | indirectly — can declare hooks and MCP servers | **project trust** |
| `.codex/hooks.json` | yes | **yes** — shell commands at lifecycle points | project trust **+ per-hook content hash** |
| `[hooks]` inline in `.codex/config.toml` | yes | **yes** | same as above |
| project execpolicy `.rules` | yes | steers command classification | `--ignore-rules` disables |
| `AGENTS.md` (and nested ones) | yes | **no** — steers the model only | none documented |
| `.codex/` skills / subagents | yes | via hooks they declare | hook trust |

Config discovery, verbatim:

> "Codex walks from the project root to your current working directory and
> loads every `.codex/config.toml` it finds. If multiple files define the same
> key, the closest file to your working directory wins."

Precedence, highest first: CLI flags → **project-local `.codex/config.toml`** →
profile (`$CODEX_HOME/<name>.config.toml`) → user `~/.codex/config.toml`. Note
this is the inverse of Claude Code, where managed settings beat the command
line: in Codex **CLI flags win outright**, which is what nox wants.

`CODEX_HOME` "defaults to `~/.codex`" and holds `config.toml`, **`auth.json`**,
`history.jsonl`, logs and caches — add `~/.codex/auth.json` to the §3 credential
table.

`AGENTS.md` is the only *unconditionally* repo-supplied input, and it only
steers the model — it is a prompt-injection surface (§1), not a code-execution
surface. I found no flag to suppress it.

## 2. Is there a `-p`-style trust bypass? **No — Codex fails closed.**

Verbatim (`learn.chatgpt.com/docs/config-file/config-advanced`):

> "For security, Codex loads project-scoped config files only when the project
> is trusted. If the project is untrusted, Codex ignores project `.codex/`
> layers, including `.codex/config.toml`, project-local hooks, and
> project-local rules."

> "Project-local hooks load only when the project `.codex/` layer is trusted."

This is the exact inverse of Claude Code's documented `-p` behaviour ("Hooks…
**Used**"; `.mcp.json` "**Connected without asking**"). Nothing in the `codex
exec` help or docs re-enables project config non-interactively.

Codex additionally blocks a set of keys in project config **regardless of
trust**, verbatim:

> "Codex ignores the following keys in project-local `.codex/config.toml`…
> `openai_base_url`, `chatgpt_base_url`, `apps_mcp_product_sku`,
> `model_provider`, `model_providers`, `notify`, `profile`, `profiles`…"

> "Project config files can't override settings that redirect credentials,
> alter host-owned app request metadata, change provider auth, select config
> profiles, or run machine-local notification/telemetry commands."

That is a designed defence against exactly the credential-redirection vector,
and **neither Claude Code nor OpenCode has an equivalent** — Claude Code's
project `env` block and `apiKeyHelper` are "Used" under `-p`.

**The caveat that matters, and it is decisive for nox.** Project trust is
scoped to a **path**, not to a **commit**. The user's own repository is a repo
they have already trusted. A hostile *branch* checked out into that same
already-trusted path therefore inherits trust for `.codex/config.toml`. Codex's
project-trust gate defends against *a new hostile repository*; nox's threat
model is *a hostile branch in a trusted repository*, which the gate does not
cover.

What saves Codex here is the **second, independent gate on hooks** (§4).

## 3. MCP servers from repo-supplied config

`mcp_servers` is **not** on the blocked-keys list, so a trusted project's
`.codex/config.toml` can declare MCP servers, and a stdio MCP entry spawns a
command. Per §2, that means a hostile branch in an already-trusted repo can
declare one.

**There is no `--strict-mcp-config` analogue.** No flag on `codex`, `codex
exec`, or `codex exec review` disables MCP loading. The available levers are
indirect:

- `--ignore-user-config` — "Do not load `$CODEX_HOME/config.toml`; auth still
  uses `CODEX_HOME`" (**P**, `codex exec --help`). Kills *user* config only —
  the wrong layer for this threat.
- `-c mcp_servers={}` — CLI flags outrank project config, and `-c` "value
  portion is parsed as TOML", so an empty-table override should clear the
  merged map. **Unverified** — I did not run it, and whether `-c` replaces or
  merges a table is not documented.

This is Codex's one genuine gap relative to Claude Code, which closes the same
hole with a documented flag.

## 4. Plugins / hooks auto-loading repo code — **the decisive question**

**Hooks exist and fire at session start.** Verbatim: "When a session or
subagent starts: `SessionStart`, `SubagentStart`". Hook sources are
`~/.codex/hooks.json`, `~/.codex/config.toml`, `<repo>/.codex/hooks.json`,
`<repo>/.codex/config.toml`.

**But hook trust is content-hashed, and untrusted hooks are skipped
non-interactively.** Verbatim (`learn.chatgpt.com/docs/hooks`):

> "Codex records trust against the hook's **current hash**, so **new or changed
> hooks are marked for review and skipped until trusted**."

> "Before a non-managed hook can run, Codex requires you to review and trust the
> exact hook definition."

> "pass `--dangerously-bypass-hook-trust` to run enabled hooks without requiring
> persisted hook trust for that invocation."

Corroborated by the CLI itself (**P**, `codex --help`):

> `--dangerously-bypass-hook-trust` — "Run enabled hooks without requiring
> persisted hook trust for this invocation. **DANGEROUS.** Intended only for
> automation that already vets hook sources"

This is the structural answer to the hostile-branch problem that path-scoped
project trust cannot give. An attacker's branch adding or editing
`.codex/hooks.json` changes the hash → the hook is untrusted → it is **skipped**
in `codex exec`. nox's obligation is simply to **never pass
`--dangerously-bypass-hook-trust`**, and to treat that flag's presence in any
user-supplied config as a hard error.

**Plugins are user-installed, not repo-loaded.** `codex plugin add
<PLUGIN[@MARKETPLACE]>` installs "from a configured marketplace snapshot"
(**P**); marketplaces are themselves explicitly registered via `codex plugin
marketplace add` ("Add a local or Git marketplace to the configured marketplace
sources"). Installation is an explicit user command recorded in user config.
Plugins can carry skills, connectors, MCP servers, browser extensions, hooks
and scheduled-task templates, and the docs say "Review and trust plugin hooks
before you enable them" — i.e. plugin hooks route through the same hash trust.

**No repo-directory plugin autoload is documented.** There is no Codex
equivalent of OpenCode's `.opencode/plugins/` "automatically loaded at startup".
That is the single difference that puts Codex on the safe side of the
asymmetry.

## 5. The sandbox — OS-level, but it contains the tool vector only

`codex --help` (**P**) is precise about scope:

> `-s, --sandbox <SANDBOX_MODE>` — "Select the sandbox policy to use when
> executing **model-generated shell commands**"
> `[possible values: read-only, workspace-write, danger-full-access]`

Mechanism per platform (secondary, corroborated across several independent
write-ups):

| Platform | Mechanism |
|---|---|
| macOS 12+ | Apple **Seatbelt** — `sandbox-exec -p <profile>` matching `--sandbox` |
| Linux | **Landlock** (read everywhere; write only to `/dev/null` and writable roots) + **seccomp** (blocks `connect`, `bind`, `sendto`…; `AF_UNIX` only). Falls back to **Bubblewrap** where Landlock is unavailable or insufficient |
| Windows | restricted token + computed allow/deny paths, **denying `.git`** |

Inside writable roots, `.git` and `.codex` are made read-only subpaths — so even
`workspace-write` cannot rewrite repo metadata or Codex config. `codex sandbox
<COMMAND>` exposes the sandbox standalone, and `codex debug landlock` /
`codex debug seatbelt` exist for inspection.

**The distinction the ADR needs:** this is a genuine OS-enforced boundary, and
it is strictly stronger than Claude Code's (on by default rather than opt-in,
and network-denying by default rather than domain-prompting). But it wraps
**model-generated shell commands**, not Codex's own startup. Config parsing,
hook loading, MCP-server spawning and plugin loading all happen in the Codex
process before and outside that boundary.

So: **the sandbox mitigates the tool vector; project trust and hook-hash trust
mitigate the config vector.** They are separate mechanisms and neither
substitutes for the other. A hook that ran would run *outside* the sandbox.

Approval policy is orthogonal (`-a/--ask-for-approval untrusted | on-request |
never`), and `never` means "Never ask for user approval. Execution failures are
immediately returned to the model" — the right choice for a non-interactive run
*only* when paired with `--sandbox read-only`, since with `never` there is no
human to escalate to.

## 6. The app-server path

`codex app-server` is marked `[experimental]` in `--help` (**P**). It is a
long-lived JSON-RPC 2.0 process — the same backend behind the VS Code and
JetBrains extensions, the Python SDK, and `openai/codex-plugin-cc`.

**`review/start` parameters:** `threadId` (required); `delivery` — `"inline"`
(default, runs on the existing thread) or `"detached"` (forks a new thread);
`target` — one of `uncommittedChanges`, `baseBranch` (with branch name),
`commit` (with SHA/title), or `custom` (with instructions).

**`review/start` takes no sandbox parameter.** It "operates within the turn
system, so it respects the thread's configured sandbox policy." Write access is
therefore governed by `sandboxPolicy` on `turn/start` / `thread/start`, whose
values are `"dangerFullAccess"`, `"readOnly"`, `"workspaceWrite"`,
`"externalSandbox"`. Per-turn config: "You can override configuration settings
per turn (model, effort, personality, `cwd`, sandbox policy, summary). When
specified, these settings become the defaults for later turns on the same
thread." `approvalPolicy` accepts `"never"`, `"unlessTrusted"`, `"onRequest"`.

**Answer to "does `review/start` grant repo write access": it inherits, it does
not grant.** A client that never sets `sandboxPolicy` gets the thread/config
default, which is *not* read-only. nox must set `sandboxPolicy: "readOnly"`
explicitly on `thread/start`, and re-assert it on `turn/start` rather than
trusting inheritance.

**Config loading in the app-server path is the weak link in this addendum.**
Secondary sources say app-server "reads configuration from `~/.codex/config.toml`
(user level) and `.codex/config.toml` (project level)" and that
filesystem-resident features "live as files Codex reads rather than RPC
methods" and "apply to every client of the app-server… automatically." But
**neither the official app-server page nor the community guide states whether
the app-server honours the project-trust and hook-trust gates**, and the
protocol exposes `config/value/write` and `config/batchWrite`, which the CLI
does not. Given that the app-server has no `--dangerously-bypass-hook-trust`
equivalent visible in `--help`, the most likely reading is that trust is
enforced in the shared core rather than the CLI front end — but that is an
inference, and it is the one fact on this axis I would not ship on.

**Recommendation for nox:** prefer `codex exec review` over the app-server for
v1. It is non-experimental, its trust behaviour is documented, and it carries
the flags that matter (`--ignore-rules`, `--ignore-user-config`, `--ephemeral`,
`--strict-config`). The app-server buys streaming and session reuse that nox's
one-shot review does not need.

## 7. Three-way asymmetry

**Question: is "safe against a hostile branch, in the same working tree, via
flags alone" achievable?**

| | Claude Code 2.1.251 | Codex 0.144.1 | OpenCode |
|---|---|---|---|
| Repo config gate under non-interactive run | **fails open** — hooks "Used", `.mcp.json` "Connected without asking" | **fails closed** — untrusted project layers ignored… but trust is **path-scoped**, so an already-trusted repo's hostile branch passes | **fails open** — project `opencode.json` outranks `OPENCODE_CONFIG` |
| Second gate on hook/plugin code | none | **content-hash hook trust — new/changed hooks skipped** | none |
| Repo-directory code autoload | no | no | **yes — `.opencode/plugins/` auto-loads at startup** |
| Off-switch for repo MCP | `--strict-mcp-config` | **none** (only `-c mcp_servers={}`, unverified) | none documented |
| Credential-key protection in project config | none — project `env` / `apiKeyHelper` used | **explicit blocked-key list** | none |
| OS-level sandbox | opt-in, off by default, degrades silently, no native Windows | **on by default**; Seatbelt / Landlock+seccomp / restricted token | none |
| **Verdict** | **Yes, via flags** | **Yes, via flags** | **No** |

**Minimum mitigation per harness:**

- **Claude Code** — `claude -p --safe-mode --restricted --strict-mcp-config
  --tools "Read,Grep,Glob" --permission-mode dontAsk`, diff on stdin, `cwd` at
  repo root, no `--add-dir`.
- **Codex** — `codex exec review --base <branch> --sandbox read-only
  --ask-for-approval never --ignore-rules --ephemeral --strict-config`, and
  **never** `--dangerously-bypass-hook-trust` or
  `--dangerously-bypass-approvals-and-sandbox`. Caveat: `-s/--sandbox` and
  `-a/--ask-for-approval` are **not** flags on `codex exec review` (see
  negatives) — set them via `-c sandbox_mode=…` or use `codex exec` with a
  review prompt. Residual accepted risk: repo-declared MCP servers in an
  already-trusted project.
- **OpenCode** — no flag set is sufficient. The only mitigation that works is
  deleting `.opencode/` and `opencode.json` from a scratch checkout before
  spawning, which requires the ephemeral worktree that the settled constraints
  exclude. Under the settled constraints, OpenCode support is "trusted diffs
  only" and should be documented as such.

The asymmetry is now **2–1, not 1–1**: Codex joins Claude Code, and OpenCode is
alone on the wrong side. That strengthens rather than weakens the case for
treating OpenCode differently in v1.

## Addendum 2 negatives

- **`codex exec review` does not expose `-s/--sandbox`, `-a/--ask-for-approval`,
  `-C/--cd`, or `--add-dir`** (verified: full option list is `-c/--config,
  --uncommitted, --base, --enable, --commit, --disable, --strict-config,
  --title, -m/--model, --dangerously-bypass-approvals-and-sandbox,
  --dangerously-bypass-hook-trust, --skip-git-repo-check, --ephemeral,
  --ignore-user-config, --ignore-rules, --output-schema, --json,
  -o/--output-last-message`). Top-level `codex review` is **weaker still** —
  it lacks even `--ignore-rules`, `--ignore-user-config` and `--ephemeral`. So
  the recommended invocation above **cannot be issued as written**; sandbox mode
  must go through `-c`. I did **not** verify the correct config key name
  (`sandbox_mode` is inferred from the `--sandbox` flag name and community
  docs, not read from official documentation).
- **`-c mcp_servers={}` is untested**, and whether `-c` replaces or deep-merges
  a TOML table is undocumented. The claim that it clears repo-declared MCP
  servers is an inference.
- **How a Codex project becomes trusted is not documented** on the pages I
  reached. The docs state trust gates project config but never say whether
  trust is granted by an interactive prompt, a `projects.<path>.trust_level`
  key, or the git-repo heuristic. My claim that trust is **path-scoped and
  therefore survives a branch switch** follows from the wording ("the project
  is trusted") and from `--skip-git-repo-check`'s existence, but I did not
  confirm it. **If trust turned out to be commit- or content-scoped, Codex
  would be strictly safer than reported here; if it is granted automatically to
  any git repo, Codex's project-config gate is weaker than reported.** This is
  the highest-value open question in this addendum.
- **Whether the app-server honours project trust and hook trust is
  undocumented** in both the official page and the community guide. Treated as
  unknown; the recommendation routes around it.
- **Sandbox platform mechanisms are secondary-source only** (independent
  write-ups, a community gist, and a third-party analysis). The official
  `learn.chatgpt.com/docs/sandbox` page returned 404 during this research. The
  *policy names* are primary (`codex --help`); the *implementation* is not.
- **`learn.chatgpt.com/docs/mcp` and `/docs/agents-md` both 404'd**, so the MCP
  and `AGENTS.md` findings rest on the config-advanced page and the plugins
  page rather than dedicated documentation.
- **No Codex command was executed beyond `--help`.** No `codex doctor`, no
  `codex debug prompt-input`, no `exec`, no auth. Every behavioural claim is
  help text or documentation, never observed behaviour — consistent with the
  rest of this file, where **no empirical test was run for any harness.**
