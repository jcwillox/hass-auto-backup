import asyncio
import logging
import os
from http import HTTPStatus
from typing import Dict, List, Optional

import aiohttp
import async_timeout
from homeassistant.components.hassio.const import X_HASSIO

from . import DEFAULT_BACKUP_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024  # 64 KB


class HassioAPIError(RuntimeError):
    """Return if a API trow a error."""


def api_data(funct):
    """Return data of an api."""

    async def _wrapper(*argv, **kwargs):
        """Wrap function."""
        data = await funct(*argv, **kwargs)
        if data["result"] == "ok":
            return data["data"]
        raise HassioAPIError(data["message"])

    return _wrapper


class HassIO:
    """Small API wrapper for Hass.io."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        web_session: aiohttp.ClientSession,
        ip: str,
    ) -> None:
        """Initialize Hass.io API."""
        self.loop = loop
        self._web_session = web_session
        self._ip = ip

    @api_data
    def get_addons_repositories(self):
        """Return data for add-ons and repositories.

        This method return a coroutine.
        """
        return self.send_command("/addons", method="get")

    async def get_addons(self) -> List[Dict]:
        result = await self.get_addons_repositories()
        return result.get("addons", [])

    async def get_installed_addons(self) -> List[Dict]:
        addons = await self.get_addons()
        return [addon for addon in addons if addon.get("installed")]

    @api_data
    def create_backup(
        self, data: Dict, partial: bool = False, timeout: Optional[int] = None
    ):
        """Create a full or partial backup.

        This method return a coroutine.
        """
        backup_type = "partial" if partial else "full"
        command = f"/backups/new/{backup_type}"
        return self.send_command(command, payload=data, timeout=timeout)

    @api_data
    def remove_backup(self, slug):
        """Remove a backup.

        This method return a coroutine.
        """
        return self.send_command(f"/backups/{slug}", method="delete", timeout=300)

    async def send_command(self, command, method="post", payload=None, timeout=10):
        """Send API command to Hass.io.

        This method is a coroutine.
        """
        try:
            with async_timeout.timeout(timeout):
                request = await self._web_session.request(
                    method,
                    f"http://{self._ip}{command}",
                    json=payload,
                    headers={X_HASSIO: os.environ.get("HASSIO_TOKEN", "")},
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

    async def download_backup(
        self, slug: str, destination: str, timeout: int = DEFAULT_BACKUP_TIMEOUT_SECONDS
    ):
        """Download and save a backup from Hass.io."""
        command = f"/backups/{slug}/download"

        try:
            with async_timeout.timeout(timeout):
                request = await self._web_session.request(
                    "get",
                    f"http://{self._ip}{command}",
                    headers={X_HASSIO: os.environ.get("HASSIO_TOKEN", "")},
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
