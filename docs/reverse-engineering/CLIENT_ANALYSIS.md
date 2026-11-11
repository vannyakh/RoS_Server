# Client analysis

OBSERVED FACT: The repository has no APK, IPA, packet capture, or native client library. `README.md` documents a browser page at `/play` served by this server.

OBSERVED FACT: On 2026-11-10 a public web search for an official client network protocol returned shutdown notices and one unofficial forum thread. The notices say Rules of Survival ceased operations on June 27, 2022. No client binary was downloaded. No packet field, handshake, or credential check was copied from the forum thread.

INTERPRETATION: The browser page is a client of this server. It is not evidence of the original mobile client. A shutdown date is not an interface specification. An unofficial forum post is not an authorized reference.

OBSERVED FACT: The sibling client repository keeps the Android game files beside this service. They stay in that repository under `Client/Decompiled` and are read-only outside the Apktool `build` folder. This server does not store a second copy of the APK, XAPK, or OBB files.

OBSERVED FACT: The inspected base package is `com.netease.chiji`, versionName `1.610637.617289`, versionCode `1227927`. The engine is NeoX. The launcher activity is `com.netease.neox.Launcher` and the game surface is `com.netease.neox.Client`, with native library `libclient.so`. Hashes are in the sibling file `Client/Documentation/PROVENANCE.md`.

OBSERVED FACT: On LDPlayer `emulator-5554` the native client opened `com.netease.neox.Client` and stayed on the patch gate text "Retrieving patch lists 0.00%". Login and lobby screens were not reached. Android XML in the package is account-SDK chrome, not the game lobby.

HYPOTHESIS: The original network protocol is not the JSON API in this service. No field from the native client has been shown to match `/api/v1` or `/api/v1/ws`.

IMPLEMENTATION IMPACT: The independent application is `Android_API_Client` in the sibling repository, package `com.ros.client`. It may call this service's documented routes. The NeoX client stays reference-only. Do not claim original-client support. Do not bypass authentication, certificate pinning, or access controls. Do not record credentials, keys, or tokens. Do not implement a protocol from an unofficial forum page.

Sources: repository listing, `README.md`, sibling `Client/Documentation/PROVENANCE.md`, `https://steamcommunity.com/app/788260/allnews/`, DIS-0011, and DIS-0012.
