import asyncio
import os

import pytest

from redbot import _update_event_loop_policy
from redbot.core import drivers, data_manager

_update_event_loop_policy()


@pytest.fixture(scope="session")
def event_loop(request):
    """Create an instance of the default event loop for entire session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    asyncio.set_event_loop(None)
    loop.close()


def _get_backend_type():
    env_var = os.getenv("RED_STORAGE_TYPE")
    if env_var == "postgres":
        return drivers.BackendType.POSTGRES
    elif env_var == "redis":
        return drivers.BackendType.REDIS
    elif env_var == "sql":
        return drivers.BackendType.SQL
    else:
        return drivers.BackendType.JSON


@pytest.fixture(scope="session", autouse=True)
async def _setup_driver():
    backend_type = _get_backend_type()
    if backend_type is drivers.BackendType.REDIS:
        storage_details = {
            "host": os.getenv("REDIS_HOST") or "localhost",
            "port": int(port) if (port := os.getenv("REDIS_PORT")) else 6379,
            "password": pw if (pw := os.getenv("REDIS_PASSWORD", "NONE")) != "NONE" else None,
            "database": int(db) if (db := os.getenv("REDIS_DATABASE")) else 0,
        }
    else:
        storage_details = {}
    data_manager.storage_type = lambda: backend_type.value
    data_manager.storage_details = lambda: storage_details
    driver_cls = drivers.get_driver_class(backend_type)
    await driver_cls.initialize(**storage_details)
    yield
    await driver_cls.teardown()
