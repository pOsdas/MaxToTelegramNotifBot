import asyncio
import signal

from app.bootstrap import build_application
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


async def async_main() -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()
    configure_logging(settings)
    logger = get_logger(__name__)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    application = await build_application(settings)
    logger.info(
        "Приложение запущено: один постоянный Chromium, интервал проверки %s секунд",
        settings.max_check_interval_seconds,
    )

    try:
        await application.run(stop_event)
    finally:
        await application.close()
        logger.info("Приложение остановлено")


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
