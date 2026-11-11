# Research policy

Research supports an independent game. It does not become a copy of a proprietary client, protocol, or asset pack.

## Evidence

- **Confirmed:** directly observed in permitted materials or reproduced by a test.
- **Inferred:** a reasonable interpretation supported by that evidence.
- **Unknown:** needs more research. Do not replace it with a guess.

A new design decision is labeled as independent. It is not labeled as an original Rules of Survival fact.

## Boundaries

- Keep original Android artifacts and `Client/Decompiled/` read-only in the client repository. Do not point a patch script at that archive.
- Do not bypass authentication, encryption, certificate pinning, or access controls on an original game client.
- Do not publish numeric opcodes, packet layouts, or handshake fields unless a reviewed design implements and tests them as this project's own protocol.
- The wire format in `docs/NETWORK_PROTOCOL.md` is this server's version 1 JSON. Research notes in `docs/reverse-engineering/` are not that protocol.
- Publisher binaries, artwork, fonts, and sounds stay out of the public tree. A source license does not cover those files.
- Do not write a home directory, drive letter, or machine address into rules, skills, or shared notes.
- Do not print secrets, password hashes, raw tokens, or session hashes.

## Tools

Package inspection, static analysis, and multiplayer-architecture references may inform a later note. Running a disassembler is a separate task. A filename or a string in a binary is not a protocol field.
