# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in Wanderlisted, please disclose it responsibly by using GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) feature for this repository.

Alternatively, you can email the maintainer directly. Please include the word **"SECURITY"** in the subject line.

### What to include in your report

To help us triage and respond quickly, please provide:

- A description of the vulnerability and its potential impact
- The component(s) affected (e.g., API layer, agent graph, RAG pipeline, MCP server)
- Step-by-step reproduction instructions
- Any proof-of-concept or exploit code (if applicable)
- Suggested remediation (if known)

### What to expect

- **Acknowledgement**: We will acknowledge receipt of your report within **48 hours**.
- **Assessment**: We will assess the severity and scope within **5 business days**.
- **Resolution**: We aim to release a fix within **30 days** for critical/high severity issues.
- **Disclosure**: We will coordinate a public disclosure date with you after a fix is available.
- **Credit**: With your permission, we will credit you in the security advisory and release notes.

## Security Considerations for This Project

Wanderlisted is an AI travel planner that interacts with several external APIs and processes user-provided travel requests. Key areas of concern include:

### Prompt Injection
The system processes free-form user input that is passed to LLM agents. Adversarial content in user messages could attempt to hijack agent behavior. The project implements prompt injection defenses — see the [Security section in README.md](README.md#security-prompt-injection).

### API Key Management
The project uses multiple third-party API keys (OpenAI, Duffel, Hotelbeds, Google Maps, etc.). **Never** commit API keys or secrets to this repository. Use environment variables and `.env` files (which are `.gitignore`d).

### Dependency Vulnerabilities
We use Dependabot to monitor Python and GitHub Actions dependencies for known CVEs. Review Dependabot alerts promptly.

### Data Handling
User travel requests may contain personal information (names, travel dates, locations). Do not log or persist PII beyond what is necessary for the session.

## Security Features Enabled

- [x] Dependabot version updates (`.github/dependabot.yml`)
- [x] Secret scanning (GitHub-managed)
- [x] Push protection (GitHub-managed)
- [x] CodeQL code scanning (`.github/workflows/codeql.yml`)
- [x] CORS restrictions on the FastAPI server
- [x] Rate limiting (20 req/session per 60s)
- [x] Request ID injection for audit logging
