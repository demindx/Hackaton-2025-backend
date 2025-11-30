import asyncio
import uuid

class TaskStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


class TaskQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.results = {}
        self.status = {}

    async def add_task(self, coro):
        task_id = str(uuid.uuid4())
        self.status[task_id] = TaskStatus.PENDING
        self.results[task_id] = None

        await self.queue.put((task_id, coro))
        return task_id

    async def worker(self):
        while True:
            task_id, coro = await self.queue.get()
            self.status[task_id] = TaskStatus.RUNNING

            try:
                result = await coro
                self.results[task_id] = result
                self.status[task_id] = TaskStatus.DONE
            except Exception as e:
                self.results[task_id] = str(e)
                self.status[task_id] = TaskStatus.ERROR

            self.queue.task_done()


task_queue = TaskQueue()
