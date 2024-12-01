import logging
import threading
import time
from typing import Callable, Dict

logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.running = True
        self._start_scheduler()

    def _start_scheduler(self):
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()

    def _scheduler_loop(self):
        while self.running:
            current_time = time.time()
            for task_id, task in list(self.tasks.items()):
                if current_time >= task['execution_time']:
                    try:
                        task['callback']()
                    except Exception as e:
                        logger.error(f"Task execution failed: {str(e)}")
                    finally:
                        if not task.get('recurring'):
                            del self.tasks[task_id]
            time.sleep(1)

    def schedule_task(self, task_id: str, callback: Callable, delay: int, recurring: bool = False):
        self.tasks[task_id] = {
            'execution_time': time.time() + delay,
            'callback': callback,
            'recurring': recurring
        }

    def stop(self):
        self.running = False