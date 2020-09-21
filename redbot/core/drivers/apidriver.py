import getpass
from typing import Any, Final, Optional, Union, AsyncIterator, Tuple

import aiohttp
from aiohttp import BytesPayload
from aiohttp.typedefs import JSONEncoder

from redbot.core import errors
from redbot.core.drivers.log import log
from secrets import compare_digest

try:
    import orjson

    ujson = None
    json_loads = orjson.loads
    json_dumps = orjson.dumps
except ImportError:
    import ujson

    orjson = None
    json_loads = ujson.loads
    json_dumps = ujson.dumps


from .base import BaseDriver, IdentifierData, ConfigCategory

__all__ = ["APIDriver"]


_GET_ENDPOINT: Final[str] = "{base}/config/get"
_AITER_COGS_ENDPOINT: Final[str] = "{base}/config/cogs"
_SET_ENDPOINT: Final[str] = "{base}/config/set"
_INCREMENT_ENDPOINT: Final[str] = "{base}/config/increment"
_TOGGLE_ENDPOINT: Final[str] = "{base}/config/toggle"
_CLEAR_ENDPOINT: Final[str] = "{base}/config/clear"
_CLEAR_ALL_ENDPOINT: Final[str] = "{base}/config/clear_all"


class JsonPayload(BytesPayload):
    def __init__(
        self,
        value: Any,
        encoding: str = "utf-8",
        content_type: str = "application/json",
        dumps: JSONEncoder = json_dumps,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if orjson:
            super().__init__(
                dumps(value), content_type=content_type, encoding=encoding, *args, **kwargs
            )
        else:
            super().__init__(
                dumps(value).encode(encoding),
                content_type=content_type,
                encoding=encoding,
                *args,
                **kwargs,
            )


# noinspection PyProtectedMember
class APIDriver(BaseDriver):
    __token: Optional[str] = None
    __base_url: Optional[str] = None
    __session: Optional[aiohttp.ClientSession] = None
    _decoder: str = "orjson" if orjson else "ujson"

    @classmethod
    async def initialize(cls, **storage_details) -> None:
        host = storage_details["host"]
        password = storage_details["password"]
        cls.__token = password
        cls.__base_url = host
        cls.__session = aiohttp.ClientSession()

    @classmethod
    async def teardown(cls) -> None:
        await cls.__session.close()

    @staticmethod
    def get_config_details():
        host = (
            input(
                f"Enter the API server's base url "
                f"If left blank, Red will try the following, in order:\n"
                f" - http://localhost:8000.\n"
                f"> "
            )
            or "http://localhost:8000"
        )
        if host.endswith("/"):
            host = host[:-1]
        password = getpass.getpass(
            f"Enter the API server password. The input will be hidden.\n"
            f"  NOTE: If the server requires no password, enter NONE (Case sensitive).\n"
            f"When NONE is entered, this will default to:\n"
            f" - No password.\n"
            f"> "
        )
        if compare_digest(password, "NONE"):
            password = None

        return {
            "host": host,
            "password": password,
        }

    async def get(self, identifier_data: IdentifierData):
        full_identifiers = identifier_data.to_dict()
        async with self.__session.post(
            url=_GET_ENDPOINT.replace("{base}", self.__base_url),
            headers={"Authorization": self.__token},
            data=JsonPayload({"identifier": full_identifiers}),
            json_serialize=self._dump_to_string,
        ) as response:
            if response.status == 200:
                return self._load_to_string(await response.json(loads=json_loads))
            else:
                raise KeyError

    async def set(self, identifier_data: IdentifierData, value=None):
        full_identifiers = identifier_data.to_dict()
        async with self.__session.put(
            url=_SET_ENDPOINT.replace("{base}", self.__base_url),
            headers={"Authorization": self.__token},
            data=JsonPayload(
                {"identifier": full_identifiers, "config_data": self._dump_to_string(value)}
            ),
            json_serialize=self._dump_to_string,
        ) as response:
            response_output = await response.json(loads=json_loads)
            if response.status == 200:
                response_output = self._load_to_string(response_output)
                return response_output.get("value")
            else:
                raise errors.ConfigError(str(response_output))

    async def clear(self, identifier_data: IdentifierData):
        full_identifiers = identifier_data.to_dict()
        async with self.__session.put(
            url=_CLEAR_ENDPOINT.replace("{base}", self.__base_url),
            headers={"Authorization": self.__token},
            data=JsonPayload({"identifier": full_identifiers}),
            json_serialize=self._dump_to_string,
        ) as response:
            response_output = await response.json(loads=json_loads)
            if response.status == 200:
                response_output = self._load_to_string(response_output)
                return response_output.get("value")
            else:
                raise errors.ConfigError(str(response_output))

    async def inc(
        self,
        identifier_data: IdentifierData,
        value: Union[int, float],
        default: Union[int, float] = 0,
    ) -> Union[int, float]:
        full_identifiers = identifier_data.to_dict()
        async with self.__session.put(
            url=_INCREMENT_ENDPOINT.replace("{base}", self.__base_url),
            headers={"Authorization": self.__token},
            data=JsonPayload(
                {
                    "identifier": full_identifiers,
                    "config_data": self._dump_to_string(value),
                    "default": self._dump_to_string(default),
                }
            ),
            json_serialize=self._dump_to_string,
        ) as response:
            response_output = await response.json(loads=json_loads)
            if response.status == 200:
                response_output = self._load_to_string(response_output)
                return response_output.get("value")
            else:
                raise errors.ConfigError(str(response_output))

    async def toggle(
        self, identifier_data: IdentifierData, value: bool = None, default: Optional[bool] = None
    ) -> bool:
        full_identifiers = identifier_data.to_dict()
        async with self.__session.put(
            url=_TOGGLE_ENDPOINT.replace("{base}", self.__base_url),
            headers={"Authorization": self.__token},
            data=JsonPayload(
                {
                    "identifier": full_identifiers,
                    "config_data": self._dump_to_string(value),
                    "default": self._dump_to_string(default),
                }
            ),
            json_serialize=self._dump_to_string,
        ) as response:
            response_output = await response.json(loads=json_loads)
            if response.status == 200:
                response_output = self._load_to_string(response_output)
                return response_output.get("value")
            else:
                raise errors.ConfigError(str(response_output))

    @classmethod
    async def delete_all_data(cls, **kwargs) -> None:
        """Delete all data being stored by this driver."""
        async with cls.__session.put(
            url=_CLEAR_ALL_ENDPOINT.replace("{base}", cls.__base_url),
            headers={"Authorization": cls.__token},
            param={"i_want_to_do_this": True},
            json_serialize=cls._dump_to_string,
        ) as response:
            response_output = await response.json(loads=json_loads)
            if response.status == 200:
                response_output = cls._load_to_string(response_output)
                return response_output.get("value")
            else:
                raise errors.ConfigError(str(response_output))

    @classmethod
    async def aiter_cogs(cls) -> AsyncIterator[Tuple[str, str]]:
        async with cls.__session.post(
            url=_AITER_COGS_ENDPOINT.replace("{base}", cls.__base_url),
            headers={"Authorization": cls.__token},
            json_serialize=cls._dump_to_string,
        ) as response:
            response_output = await response.json(loads=json_loads)
            return cls._load_to_string(response_output)

    async def import_data(self, cog_data, custom_group_data):
        log.info(f"Converting Cog: {self.cog_name}")
        for category, all_data in cog_data:
            log.info(f"Converting cog category: {category}")
            ident_data = IdentifierData(
                self.cog_name,
                self.unique_cog_identifier,
                category,
                (),
                (),
                *ConfigCategory.get_pkey_info(category, custom_group_data),
            )
            try:
                await self.set(ident_data, all_data)
            except Exception:
                await self._individual_migrate(category, custom_group_data, all_data)

    async def _individual_migrate(self, category, custom_group_data, all_data):
        splitted_pkey = self._split_primary_key(category, custom_group_data, all_data)
        for pkey, data in splitted_pkey:
            ident_data = IdentifierData(
                self.cog_name,
                self.unique_cog_identifier,
                category,
                pkey,
                (),
                *ConfigCategory.get_pkey_info(category, custom_group_data),
            )
            try:
                await self.set(ident_data, data)
            except Exception as err:
                log.critical(f"Error saving: {ident_data.__repr__()}: {data}", exc_info=err)

    @staticmethod
    def _load_to_string(value: Any) -> Any:
        if not orjson:
            return value
        if hasattr(value, "decode"):
            return value.decode("utf-8")
        return value

    @staticmethod
    def _dump_to_string(value: Any) -> Any:
        if not orjson:
            return ujson.dumps(value)
        else:
            return orjson.dumps(value).decode("utf-8")
