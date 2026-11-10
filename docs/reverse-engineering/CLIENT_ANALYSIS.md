# Client analysis

OBSERVED FACT: The repository has no APK, IPA, packet capture, or native client library. `README.md` documents a browser page at `/play` served by this server.

OBSERVED FACT: On 2026-11-10 a public web search for an official client network protocol returned shutdown notices and one unofficial forum thread. The notices say Rules of Survival ceased operations on June 27, 2022. No client binary was downloaded. No packet field, handshake, or credential check was copied from the forum thread.

INTERPRETATION: The browser page is a client of this server. It is not evidence of the original mobile client. A shutdown date is not an interface specification. An unofficial forum post is not an authorized reference.

OBSERVED FACT: A sibling client tree exists outside this repository. Its original packages and Apktool extract sit under that tree's `Client/Decompiled` and are read-only outside the Apktool `build` folder. This server has not adopted its protocol.

HYPOTHESIS: A user-owned authorized client could be inspected later. The sibling archive is reference material only.

IMPLEMENTATION IMPACT: Do not claim original-client support. Do not bypass authentication, certificate pinning, or access controls. Do not record credentials, keys, or tokens. Do not implement a protocol from the unofficial forum page.

Sources: repository listing, `README.md`, `https://steamcommunity.com/app/788260/allnews/`, and the search recorded as DIS-0011.
