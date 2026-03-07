from __future__ import annotations

import time


class MemoryCooldownStore:
    def __init__(self):
        self._exp: dict[str, float] = {}

    async def ttl(self, key: str) -> int:
        now = time.time()
        exp = self._exp.get(key)
        if exp is None:
            return -2
        if exp <= now:
            self._exp.pop(key, None)
            return -2
        return int(exp - now)

    async def set(self, key: str, value: str, ex: int) -> None:
        self._exp[key] = time.time() + max(1, int(ex))

    async def delete(self, key: str) -> None:
        self._exp.pop(key, None)
