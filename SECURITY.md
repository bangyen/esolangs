# Security policy

## Supported versions

The latest release on PyPI and the current `main` branch. There are no
maintenance branches for older versions.

## What is in scope

This project runs esoteric-language programs. Interpreters execute untrusted
input by design, so a program producing wrong output, looping forever, or
exhausting memory is a correctness bug — please open a normal issue for those.

In scope for a security report is anything that escapes the interpreter:

- executing arbitrary code on the host, or reading or writing files outside
  what a run was given
- a crash in a native reference interpreter (`extra/rust/`) that indicates
  memory unsafety
- code execution through the CLI's file or language arguments
- a compromise in the release pipeline or a published artifact

## Reporting

Report privately through GitHub's
[security advisory form](https://github.com/bangyen/esolangs/security/advisories/new),
not a public issue.

Please include the language, the smallest program that shows it, the commit or
released version, and what the program achieved that it should not have been
able to.

Expect an acknowledgement within a week. Since this is a personal project
maintained in spare time, a fix may take longer; you will get an honest
estimate rather than silence.
