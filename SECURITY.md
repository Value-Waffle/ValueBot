# Security policy

## Supported versions

valuebot is pre-1.0. Security fixes land on the latest minor release only.

| Version | Supported |
|:---|:---|
| 0.2.x (current) | ✅ |
| < 0.2 | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** A public issue
gives an attacker the details before a fix exists.

Report it through GitHub's private reporting:

1. Go to the **Security** tab of the repository.
2. Click **Report a vulnerability**.
3. Describe the issue, the version affected, and how to reproduce it.

If private reporting is unavailable, open a regular issue that says only
"security report — please open a private channel" and nothing more. A
maintainer will respond with a private route.

Please include, where you can:

- the affected version and deployment (Docker, bare metal)
- what an attacker gains, and what access they need
- steps to reproduce, or a proof of concept
- whether the issue is already public

### What to expect

| Stage | Target |
|:---|:---|
| Acknowledgement | 3 business days |
| Initial assessment and severity rating | 10 business days |
| Fix and release | Agreed with the reporter, prioritised by severity |
| Disclosure | Coordinated with the reporter, after the fix ships |

We will keep you updated, and we will credit you in the release notes unless
you would rather stay anonymous.

## Scope

**In scope**

| Area | Examples |
|:---|:---|
| The MCP server | Injection through filing content, path traversal in a tool argument, a tool escaping its module boundary |
| The identity file | Reading or overwriting `identity.json` from an unintended path; a permissions flaw that exposes it |
| The plugin manifests | A tampered `plugin.json` or `mcp.json`; a dependency-confusion vector |
| The data layer | SQL injection, an unvalidated path outside the allowed root, a write outside `${PLUGIN_DATA}` |
| The setup script | Privilege issues, writing outside the intended directory |

**Out of scope**

| Area | Why |
|:---|:---|
| The SEC's own data | A filing that is wrong, late, or mis-tagged is the issuer's problem, not a vulnerability in valuebot |
| Unavoidable behaviour of an upstream dependency | Report it upstream; tell us if you believe we pin it unsafely |
| Missing hardening headers on a locally-served page | valuebot is an MCP server, not a web application |
| Denial of service through legitimate heavy use | Raise it as a feature request |
| Findings from an automated scan with no demonstrated impact | Report with a working proof of concept and we will take a look |

## Out of scope: what valuebot deliberately does not do

These are design decisions, not vulnerabilities. Reporting them is not useful.

| valuebot does not | Why |
|:---|:---|
| Execute anything from a filing | Filing text is data. It is never passed to a shell, an evaluator, or a template engine. |
| Fetch arbitrary URLs | Tools address SEC endpoints by issuer, not by caller-supplied URL. |
| Write outside `${PLUGIN_DATA}` | The plugin folder is treated as read-only at runtime. |
| Hold or transmit credentials | The only secret is the SEC User-Agent string, and it is a contact address, not a credential. |

## Hardening your own deployment

valuebot is designed to run with a narrow blast radius.

| Measure | How |
|:---|:---|
| Run the container as a non-root user | The official LibreChat image already does. Do not override it. |
| Keep the data directory on a private volume | `${PLUGIN_DATA}` holds `identity.json` and cached filings. It is not meant to be world-readable. |
| Do not expose the MCP server over a network | It is a stdio server. It speaks JSON-RPC on stdin/stdout and has no authentication. |
| Use a dedicated contact address | The SEC User-Agent is a mailbox you control. |
| Keep the plugin folder read-only at runtime | valuebot never writes to it. A read-only mount proves it. |
| Review the release before upgrading | Compare `plugin.json` and `mcp.json` versions; a mismatch disables the MCP server. |

## Responsible disclosure

We ask that you give us a reasonable opportunity to fix an issue before
disclosing it publicly. We will not pursue legal action against good-faith
research that respects that request, stays within the scope above, and does not
degrade the availability of the service for other users.
