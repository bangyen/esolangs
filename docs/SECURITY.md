# Security policy

## Supported versions

The latest PyPI release and `main`; older versions are unsupported.

## What is in scope

Wrong output, loops, and resource exhaustion are correctness bugs; use a
normal issue.

In scope for a security report is anything that escapes the interpreter:

- executing arbitrary code on the host, or reading or writing files outside
  what a run was given
- a crash in a native reference interpreter (`extra/assembly/`) that
  indicates memory unsafety
- code execution through the CLI's file or language arguments
- a compromise in the release pipeline or a published artifact

## Reporting

Use GitHub's private
[security advisory form](https://github.com/bangyen/esolangs/security/advisories/new).

Include the language, smallest reproducer, version, and impact.

Expect acknowledgement within a week; a fix may take longer.
