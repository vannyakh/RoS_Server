"""HTTP helpers for the server's own API. Not an official game client."""

async def register(client, username: str, password: str):
    return await client.post("/api/v1/auth/register", json={"username": username, "password": password})


async def login(client, username: str, password: str):
    return await client.post("/api/v1/auth/login", json={"username": username, "password": password})


async def profile(client, token: str):
    return await client.get("/api/v1/players/me", headers={"Authorization": f"Bearer {token}"})
