"""
agents/agent_queue.py — priority-ordered execution queue for scheduled and
ad-hoc agent runs. Single background worker thread (matches the single
gunicorn worker this app deploys with) so agent runs never overlap.

Priorities: CRITICAL > HIGH > NORMAL > LOW (lower int = runs first).
"""
import heapq
import itertools
import logging
import random
import threading
import time

log = logging.getLogger(__name__)

CRITICAL = 0
HIGH     = 1
NORMAL   = 2
LOW      = 3

_PRIORITY_NAMES = {CRITICAL: 'CRITICAL', HIGH: 'HIGH', NORMAL: 'NORMAL', LOW: 'LOW'}


class AgentQueue:
    def __init__(self, run_agent_fn, council, oracle, db):
        self.run_agent_fn = run_agent_fn
        self.council = council
        self.oracle  = oracle
        self.db      = db

        self._heap = []                      # (priority, seq, entry)
        self._seq  = itertools.count()
        self._pending_names = set()           # dedup: agent names currently queued
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._worker = None
        self._running = False
        self._history = []                    # small ring buffer for /api/queue status

    # ── PUBLIC API ──────────────────────────────────────────────────────

    def start(self):
        if self._worker and self._worker.is_alive():
            return
        self._running = True
        self._worker = threading.Thread(target=self._work_loop, daemon=True)
        self._worker.start()
        log.info("AgentQueue worker started")

    def _ensure_alive(self):
        if not (self._worker and self._worker.is_alive()):
            log.warning("AgentQueue: worker thread found dead — restarting it")
            self.start()

    def stop(self):
        self._running = False
        self._wake.set()

    def enqueue(self, name, priority=NORMAL, reason='', run_fn=None):
        """Queue an agent (or arbitrary run_fn) for execution. Non-CRITICAL
        entries are deduped by name — if it's already pending, this is a
        no-op rather than a second queued run."""
        self._ensure_alive()
        with self._lock:
            if priority != CRITICAL and name in self._pending_names:
                return False
            entry = {
                'name': name, 'priority': priority, 'reason': reason,
                'run_fn': run_fn, 'queued_at': time.time(),
            }
            heapq.heappush(self._heap, (priority, next(self._seq), entry))
            self._pending_names.add(name)
        self._wake.set()
        return True

    def enqueue_condition(self, agent_name, run_fn, reason=''):
        """CRITICAL-priority entry for a COUNCIL_CONDITIONS trigger — jumps
        the queue and bypasses the normal dedup/backpressure path, since
        these are rare, high-value, and explicitly rate-limited upstream
        (check_condition_triggers only fires once per 12h per condition)."""
        self._ensure_alive()
        with self._lock:
            entry = {
                'name': agent_name, 'priority': CRITICAL, 'reason': reason,
                'run_fn': run_fn, 'queued_at': time.time(),
            }
            heapq.heappush(self._heap, (CRITICAL, next(self._seq), entry))
        self._wake.set()
        return True

    def status(self):
        with self._lock:
            pending = [
                {'name': e['name'], 'priority': _PRIORITY_NAMES.get(p, p), 'reason': e['reason']}
                for (p, _, e) in sorted(self._heap)
            ]
            recent = list(self._history[-15:])
        alive = bool(self._worker and self._worker.is_alive())
        return {
            'running': self._running,
            'worker_alive': alive,
            'pending_count': len(pending),
            'pending': pending,
            'recent': recent,
        }

    # ── WORKER LOOP ─────────────────────────────────────────────────────

    def _work_loop(self):
        log.info("AgentQueue._work_loop entered")
        while self._running:
            try:
                entry = self._pop_next()
                if entry is None:
                    self._wake.wait(timeout=30)
                    self._wake.clear()
                    continue

                # Small jitter so scheduler bursts (many agents enqueued at
                # once by APScheduler) don't all fire in the same instant.
                if entry['priority'] != CRITICAL:
                    time.sleep(random.uniform(0.2, 1.5))

                # Budget backpressure — CRITICAL bypasses this (matches the
                # comment at the enqueue_condition call site in app.py).
                if entry['priority'] != CRITICAL and not self._budget_ok(entry['name']):
                    log.info(f"AgentQueue: skipping {entry['name']} — daily budget exhausted")
                    self._record(entry, status='skipped_budget')
                    continue

                self._run_entry(entry)
            except Exception as e:
                # Nothing inside this loop should ever be able to kill the
                # worker thread outright — log it and keep going.
                log.error(f"AgentQueue: _work_loop iteration crashed: {e}")
                time.sleep(1)
        log.warning("AgentQueue._work_loop exited — self._running is False")

    def _pop_next(self):
        with self._lock:
            if not self._heap:
                return None
            _, _, entry = heapq.heappop(self._heap)
            self._pending_names.discard(entry['name'])
            return entry

    def _budget_ok(self, name):
        try:
            from agents.llm_gateway import can_spend
            base_name = name.split(':')[0]  # e.g. 'COUNCIL:agoa_deadline_action' -> 'COUNCIL'
            return can_spend(base_name, 0)
        except Exception:
            return True  # never let a missing budget check block a run

    def _run_entry(self, entry):
        name = entry['name']
        try:
            if entry.get('run_fn'):
                entry['run_fn']()
            else:
                self.run_agent_fn(name)
            self._record(entry, status='ok')
        except Exception as e:
            log.error(f"AgentQueue: run failed for {name}: {e}")
            self._record(entry, status='error', error=str(e))

    def _record(self, entry, status, error=None):
        self._history.append({
            'name': entry['name'], 'reason': entry['reason'],
            'status': status, 'error': error,
            'finished_at': time.time(),
        })
        self._history = self._history[-50:]
