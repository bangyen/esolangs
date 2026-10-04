# Security policy

Security fixes cover the latest PyPI release and `main`.

Report interpreter escapes:

- executing arbitrary code on the host, or reading or writing files outside
  what a run was given;
- code execution through the CLI's file or language arguments;
- a compromise in the release pipeline or a published artifact.

For wrong output, loops, or resource exhaustion, open a normal issue.

Use GitHub's private [security advisory
form](https://github.com/bangyen/esolangs/security/advisories/new). Include
the language, version, impact, and smallest reproducer.

Expect prompt acknowledgement; fixes may take longer.
