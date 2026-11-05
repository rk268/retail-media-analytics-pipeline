"""POSIX single-host lock regression tests; no Spark required."""
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from src.pipeline_lock import PipelineAlreadyRunning, pipeline_lock


def _try_lock(path: str, result_queue) -> None:
    try:
        with pipeline_lock(path):
            result_queue.put("acquired")
    except PipelineAlreadyRunning:
        result_queue.put("busy")


class PipelineLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested" / "pipeline.lock"

    def _child_result(self):
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        process = ctx.Process(target=_try_lock, args=(str(self.path), queue))
        process.start()
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join()
            self.fail("Child process hung")
        self.assertEqual(process.exitcode, 0)
        return queue.get(timeout=2)

    def test_second_process_cannot_enter(self):
        with pipeline_lock(self.path):
            self.assertEqual(self._child_result(), "busy")

    def test_lock_released_after_context(self):
        with pipeline_lock(self.path):
            pass
        self.assertEqual(self._child_result(), "acquired")

    def test_exception_releases_lock(self):
        with self.assertRaisesRegex(RuntimeError, "demo"):
            with pipeline_lock(self.path):
                raise RuntimeError("demo")
        self.assertEqual(self._child_result(), "acquired")

    def test_file_presence_is_not_a_lock(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("stale metadata")
        with pipeline_lock(self.path):
            self.assertTrue(self.path.exists())
        self.assertEqual(self._child_result(), "acquired")


if __name__ == "__main__":
    unittest.main()
