from redis import Redis
from rq import Queue

import config

QUEUE_NAME = "scan_jobs"

_redis_conn: Redis | None = None
_scan_queue: Queue | None = None


def get_redis_connection() -> Redis:
    global _redis_conn

    if _redis_conn is None:
        if not config.REDIS_URL:
            raise RuntimeError("REDIS_URL não configurado.")
        _redis_conn = Redis.from_url(config.REDIS_URL)

    return _redis_conn


def get_scan_queue() -> Queue:
    global _scan_queue

    if _scan_queue is None:
        _scan_queue = Queue(QUEUE_NAME, connection=get_redis_connection())

    return _scan_queue
