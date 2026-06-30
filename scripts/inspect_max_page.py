import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.integrations.max_web.browser import PersistentBrowser
from app.integrations.max_web.client import MaxWebClient


async def main() -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()
    configure_logging(settings)

    browser = PersistentBrowser(settings)
    client = MaxWebClient(settings, browser)
    try:
        await client.start()
        probe = await client.auth_status()
        print(f"Авторизация: {probe.status.value}; {probe.reason}; {probe.url}")
        paths = await client.save_diagnostics("manual_inspect")
        print("Сохранено:")
        for path in paths:
            print(f"  {path}")
        if probe.status.value == "authorized":
            snapshot = await client.scan_unread()
            print(snapshot.model_dump_json(indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
