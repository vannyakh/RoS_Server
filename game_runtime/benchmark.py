"""Tick cost of the current Python simulation. This does not start a match server."""

import asyncio
from time import perf_counter

from game_runtime.session import AuthoritativeSession


async def measure(ticks: int = 600) -> dict[str, float | int]:
    session = AuthoritativeSession()
    await session.start("alpha", "bravo")
    await session.command("alpha", 1, 0)
    await session.command("bravo", -1, 0)
    started = perf_counter()
    for _ in range(ticks):
        await session.tick(1 / 20)
    elapsed = perf_counter() - started
    return {
        "ticks": ticks,
        "players": 2,
        "elapsed_s": round(elapsed, 6),
        "mean_ms": round(elapsed / ticks * 1000, 4),
        "simulated_tick_hz": 20,
    }


def main() -> None:
    result = asyncio.run(measure())
    print(
        f"ticks={result['ticks']} players={result['players']} "
        f"elapsed_s={result['elapsed_s']} mean_ms={result['mean_ms']}"
    )


if __name__ == "__main__":
    main()
