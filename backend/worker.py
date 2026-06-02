import logging
import platform

from redis import Redis
from rq import SimpleWorker, Worker

import config
from services.queue import QUEUE_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    if not config.REDIS_URL:
        raise SystemExit("REDIS_URL não configurado.")

    if not config.is_supabase_configured():
        raise SystemExit("Supabase não configurado (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).")

    if not config.is_openai_key_configured():
        logger.warning("OPENAI_API_KEY pode não estar configurada corretamente.")

    redis_conn = Redis.from_url(config.REDIS_URL)

    # macOS: RQ Worker usa fork() e crasha com libs Objective-C (OpenAI/httpx).
    # SimpleWorker roda jobs no mesmo processo — ok para dev local.
    if platform.system() == "Darwin":
        worker: Worker | SimpleWorker = SimpleWorker([QUEUE_NAME], connection=redis_conn)
        logger.info("Worker iniciado (SimpleWorker/macOS) — fila: %s", QUEUE_NAME)
    else:
        worker = Worker([QUEUE_NAME], connection=redis_conn)
        logger.info("Worker iniciado — fila: %s", QUEUE_NAME)

    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
