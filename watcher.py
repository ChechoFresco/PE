# watcher.py
"""Event-driven agenda monitor: watches MongoDB change streams for new agenda
documents and triggers email digests the moment files are added."""
import threading
import time
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

META_ID = "agenda_watch"
FLUSH_IDLE_SECONDS = 5      # send a digest after this much quiet time
FLUSH_MAX_BATCH = 50        # ...or as soon as this many items accumulate
CATCHUP_LIMIT = 5000


def start_watcher(app, mongo, mail):
    """Start the change-stream watcher thread (one per process)."""
    thread = threading.Thread(
        target=_run,
        args=(app, mongo, mail),
        daemon=True,
        name="agenda-watcher",
    )
    thread.start()
    logger.info("Agenda change-stream watcher started")
    return thread


def _meta(mongo):
    return mongo.db.app_meta.find_one({"_id": META_ID}) or {}


def _save_meta(mongo, last_id, resume_token=None):
    update = {"$set": {"last_id": last_id, "updated_at": time.time()}}
    if resume_token is not None:
        update["$set"]["resume_token"] = resume_token
    mongo.db.app_meta.update_one({"_id": META_ID}, update, upsert=True)


def _init_watermark(mongo):
    """First run: start after the newest existing agenda so the back
    catalog never triggers emails."""
    if _meta(mongo).get("last_id"):
        return
    last = mongo.db.Agenda.find_one({}, {"_id": 1}, sort=[("_id", -1)])
    _save_meta(mongo, last["_id"] if last else ObjectId())
    logger.info("Watcher watermark initialized (starting after newest existing agenda)")


def _catch_up(mongo, mail):
    """Process anything inserted while the watcher was down."""
    meta = _meta(mongo)
    last_id = meta.get("last_id")
    if not last_id:
        return
    new_docs = list(
        mongo.db.Agenda.find({"_id": {"$gt": last_id}})
        .sort("_id", 1)
        .limit(CATCHUP_LIMIT)
    )
    if not new_docs:
        return
    logger.info("Catch-up: %d agenda(s) inserted while watcher was down", len(new_docs))
    from jobs import process_new_agendas
    process_new_agendas(mongo, mail, new_docs)
    _save_meta(mongo, new_docs[-1]["_id"], meta.get("resume_token"))


def _flush(mongo, mail, stream, docs):
    from jobs import process_new_agendas
    logger.info("Watcher flush: %d new agenda(s)", len(docs))
    try:
        process_new_agendas(mongo, mail, docs)
    except Exception as e:
        logger.error("Watcher flush failed: %s", e)
    token = stream.resume_token
    _save_meta(mongo, docs[-1]["_id"], token)


def _watch(mongo, mail):
    meta = _meta(mongo)
    opts = {"max_await_time_ms": 1000}
    if meta.get("resume_token"):
        opts["resume_after"] = meta["resume_token"]

    stream = mongo.db.Agenda.watch(
        [{"$match": {"operationType": "insert"}}],
        **opts,
    )
    pending = []
    last_event = time.time()

    with stream:
        while True:
            change = stream.try_next()
            if change is not None:
                pending.append(change["fullDocument"])
                last_event = time.time()
                if len(pending) >= FLUSH_MAX_BATCH:
                    _flush(mongo, mail, stream, pending)
                    pending = []
            else:
                if pending and (time.time() - last_event) >= FLUSH_IDLE_SECONDS:
                    _flush(mongo, mail, stream, pending)
                    pending = []
                time.sleep(0.5)


def _run(app, mongo, mail):
    with app.app_context():
        try:
            _init_watermark(mongo)
            _catch_up(mongo, mail)
        except Exception as e:
            logger.error("Watcher startup failed: %s", e)

        while True:
            try:
                _watch(mongo, mail)
            except Exception as e:
                logger.error("Watcher error: %s; restarting in 10s", e)
                time.sleep(10)
