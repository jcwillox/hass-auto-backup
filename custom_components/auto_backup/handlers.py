import asyncio
import logging
import shutil
from http import HTTPStatus
from os import getenv
from typing import Dict, List, Optional

import aiohttp
import async_timeout
from aiohttp.hdrs import AUTHORIZATION
from homeassistant.components.backup import BackupManager
from homeassistant.const import ATTR_NAME
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_BACKUP_TIMEOUT_SECONDS, PATCH_NAME

_LOGGER = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024  # 64 KB


class HassioAPIError(RuntimeError):
    """Return if an API throws an error."""


def api_data(funct):
    """Return data of an api."""

    async def _wrapper(*argv, **kwargs):
        """Wrap function."""
        data = await funct(*argv, **kwargs)
        if data["result"] == "ok":
            return data["data"]
        raise HassioAPIError(data["message"])

    return _wrapper


class HandlerBase:
    async def get_addons(self) -> List[Dict]:
        """Returns a list of the installed addons."""
        raise NotImplementedError

    async def create_backup(
        self, data: Dict, partial: bool = False, timeout: Optional[int] = None
    ) -> Dict:
        """Create a full or partial backup.

        This method return a coroutine.
        """
        raise NotImplementedError

    def remove_backup(self, slug):
        """Remove a backup.

        This method return a coroutine.
        """
        raise NotImplementedError

    async def download_backup(
        self, slug: str, destination: str, timeout: int = DEFAULT_BACKUP_TIMEOUT_SECONDS
    ):
        """Download and save a backup from Hass.io."""
        raise NotImplementedError


class SupervisorHandler(HandlerBase):
    """Small API wrapper for Hass.io."""

    def __init__(self, ip: str, session: aiohttp.ClientSession) -> None:
        """Initialize Hass.io API."""
        self._ip = ip
        self._session = session
        self._headers = {AUTHORIZATION: f"Bearer {getenv('SUPERVISOR_TOKEN')}"}

    async def send_command(self, command, method="post", payload=None, timeout=10):
        """Send API command to Hass.io.

        This method is a coroutine.
        """
        try:
            with async_timeout.timeout(timeout):
                request = await self._session.request(
                    method,
                    f"http://{self._ip}{command}",
                    json=payload,
                    headers=self._headers,
                    timeout=None,
                )

                if request.status not in (HTTPStatus.OK, HTTPStatus.BAD_REQUEST):
                    _LOGGER.error("%s return code %d.", command, request.status)
                    raise HassioAPIError()

                answer = await request.json()
                return answer

        except asyncio.TimeoutError:
            raise HassioAPIError("Timeout on %s request" % command)

        except aiohttp.ClientError as err:
            raise HassioAPIError("Client error on %s request %s" % (command, err))

        raise HassioAPIError("Failed to call %s" % command)

    @api_data
    def _get_addons_repositories(self):
        return self.send_command("/addons", method="get")

    async def get_addons(self) -> List[Dict]:
        result = await self._get_addons_repositories()
        return [
            addon for addon in result.get("addons", []) if addon.get("installed", True)
        ]

    @api_data
    def create_backup(
        self, data: Dict, partial: bool = False, timeout: Optional[int] = None
    ):
        backup_type = "partial" if partial else "full"
        command = f"/backups/new/{backup_type}"
        return self.send_command(command, payload=data, timeout=timeout)

    @api_data
    def remove_backup(self, slug):
        return self.send_command(f"/backups/{slug}", method="delete", timeout=300)

    async def download_backup(
        self, slug: str, destination: str, timeout: int = DEFAULT_BACKUP_TIMEOUT_SECONDS
    ):
        command = f"/backups/{slug}/download"

        try:
            with async_timeout.timeout(timeout):
                request = await self._session.request(
                    "get",
                    f"http://{self._ip}{command}",
                    headers=self._headers,
                    timeout=None,
                )

                if request.status not in (200, 400):
                    _LOGGER.error("%s return code %d.", command, request.status)
                    raise HassioAPIError()

                with open(destination, "wb") as file:
                    while True:
                        chunk = await request.content.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        file.write(chunk)

                _LOGGER.info("Downloaded backup '%s' to '%s'", slug, destination)
                return

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        except IOError:
            _LOGGER.error("Failed to download backup '%s' to '%s'", slug, destination)

        raise HassioAPIError(
            "Backup download failed. Check the logs for more information."
        )


class BackupHandler(HandlerBase):
    def __init__(self, manager: BackupManager):
        self._manager = manager

    async def get_addons(self):
        raise NotImplementedError("This should be unreachable")

    # noinspection PyProtectedMember
    async def create_backup(
        self, config: Dict, partial: bool = False, timeout: Optional[int] = None
    ) -> Dict:
        if not config.get(PATCH_NAME):
            backup = await self._manager.generate_backup()
        else:
            _LOGGER.debug("Support name is set: %s", config)
            if not hasattr(self._manager, "_mkdir_and_generate_backup_contents"):
                if not hasattr(self._manager, "_generate_backup_contents"):
                    raise HomeAssistantError(
                        "Unable to patch '_generate_backup_contents' function."
                    )
                raise HomeAssistantError(
                    "Unable to patch '_mkdir_and_generate_backup_contents' function."
                )

            def wrapper(*args, **kwargs):
                if len(args) != 2 or kwargs or not isinstance(args[1], dict):
                    raise HomeAssistantError(
                        "Wrapper of '_mkdir_and_generate_backup_contents' called with wrong arguments"
                    )

                args[1]["name"] = config[ATTR_NAME]
                return old_function(*args, **kwargs)

            if hasattr(self._manager, "_generate_backup_contents"):
                old_function = self._manager._generate_backup_contents
            else:
                old_function = self._manager._mkdir_and_generate_backup_contents

            try:
                if hasattr(self._manager, "_generate_backup_contents"):
                    self._manager._generate_backup_contents = wrapper
                else:
                    self._manager._mkdir_and_generate_backup_contents = wrapper
                backup = await self._manager.generate_backup()
                backup.name = config[ATTR_NAME]
            finally:
                if hasattr(self._manager, "_generate_backup_contents"):
                    self._manager._generate_backup_contents = old_function
                else:
                    self._manager._mkdir_and_generate_backup_contents = old_function

        return backup.as_dict()

    async def remove_backup(self, slug):
        await self._manager.remove_backup(slug)

    async def download_backup(
        self, slug: str, destination: str, timeout: int = DEFAULT_BACKUP_TIMEOUT_SECONDS
    ):
        backup = await self._manager.get_backup(slug)
        if backup:
            shutil.copyfile(backup.path, destination)
        else:
            _LOGGER.error(
                "Cannot move backup (%s) to '%s' as it does not exist.",
                slug,
                destination,
            )
