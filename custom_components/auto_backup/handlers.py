import asyncio
import logging
import shutil
from dataclasses import asdict
from http import HTTPStatus
from os import getenv
from typing import Dict, List, Optional

import aiofiles
import aiohttp
from aiohttp.hdrs import AUTHORIZATION
from homeassistant.components.backup.manager import BackupManager
from homeassistant.components.hassio import (
    ATTR_PASSWORD,
    ATTR_HOMEASSISTANT_EXCLUDE_DATABASE,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant

from .const import DEFAULT_BACKUP_TIMEOUT_SECONDS

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
            async with asyncio.timeout(timeout):
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

        except TimeoutError:
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
            async with asyncio.timeout(timeout):
                request = await self._session.request(
                    "get",
                    f"http://{self._ip}{command}",
                    headers=self._headers,
                    timeout=None,
                )

                if request.status not in (200, 400):
                    _LOGGER.error("%s return code %d.", command, request.status)
                    raise HassioAPIError()

                async with aiofiles.open(destination, "wb") as file:
                    while True:
                        chunk = await request.content.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        await file.write(chunk)

                _LOGGER.info("Downloaded backup '%s' to '%s'", slug, destination)
                return

        except TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        except IOError:
            _LOGGER.error("Failed to download backup '%s' to '%s'", slug, destination)

        raise HassioAPIError(
            "Backup download failed. Check the logs for more information."
        )


class BackupHandler(HandlerBase):
    def __init__(self, hass: HomeAssistant, manager: BackupManager):
        self._hass = hass
        self._manager = manager

    async def get_addons(self):
        raise NotImplementedError("This should be unreachable")

    # noinspection PyProtectedMember
    async def create_backup(
        self, config: Dict, partial: bool = False, timeout: Optional[int] = None
    ) -> Dict:
        agent_id = list(self._manager.local_backup_agents)[0]
        backup = await self._manager.async_create_backup(
            agent_ids=[agent_id],
            name=config.get(ATTR_NAME),
            include_database=not config.get(ATTR_HOMEASSISTANT_EXCLUDE_DATABASE, False),
            include_folders=None,
            include_homeassistant=True,
            password=config.get(ATTR_PASSWORD),
            # don't exist on HA Core
            include_all_addons=False,
            include_addons=None,
        )
        [backup, agent_errors] = await self._manager.async_get_backup(
            backup.backup_job_id
        )

        return {"slug": backup.backup_id, **asdict(backup)}

    async def remove_backup(self, slug):
        await self._manager.async_delete_backup(slug)

    async def download_backup(
        self, slug: str, destination: str, timeout: int = DEFAULT_BACKUP_TIMEOUT_SECONDS
    ):
        [backup, agent_errors] = await self._manager.async_get_backup(slug)
        if backup:
            agent_id = list(self._manager.local_backup_agents)[0]
            agent = self._manager.local_backup_agents[agent_id]
            backup_path = agent.get_backup_path(backup.backup_id)

            def _copyfile():
                shutil.copyfile(backup_path, destination)

            await self._hass.async_add_executor_job(_copyfile)
        else:
            _LOGGER.error(
                "Cannot move backup (%s) to '%s' as it does not exist.",
                slug,
                destination,
            )
