# Security policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue: use the
**Report a vulnerability** button on the repository's
[Security tab](../../security/advisories/new). Only the maintainer sees it.

This is a small project maintained in spare time. I will read and answer
reports as soon as I can, but cannot promise a response time.

What counts: a way for a crafted system file or command-line argument to make
the tools do something they should not (run code, write outside the requested
output file, and similar). The tools read local files, make no network
connections and use only the Python standard library, so the attack surface is
small.

## Wrong results are ordinary bugs

If the checker misses a cross-operation, or the solver returns a key that
conflicts, that is a correctness bug, not a vulnerability. Please open a regular
[issue](../../issues/new/choose) with a **made-up** example that reproduces it.
A bug report never needs your real keys, so do not include them.

## Please never post real key data

Issues, pull requests, discussions and security reports can be public or can
leak. Do not include real bittings, real system files, or anything that
identifies a building, its residents or its keys. Anyone who sees them could
learn how a real lock system is keyed. Use `system.example.json` or invented
values. If a report seems to need real data, describe the situation in words
instead and we will find a safe example together.

## Protecting your own system files

A real system file lists the bittings of a real key system. Treat it like a
password file: keep it outside any repository (this one ignores `.json`,
`.csv` and `.txt` files and refuses to commit them, as it does PDFs and images,
but your other repositories will not), and restrict who can read it. Scans and
photos of pinning charts are just as sensitive as the system file.

## Supported versions

The project is pre-1.0: only the latest commit on `main` is supported.
