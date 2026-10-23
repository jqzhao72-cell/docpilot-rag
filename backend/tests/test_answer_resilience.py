"""Offline checks for bounded waits, non-retry and empty-answer handling."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from filelock import FileLock
from openai import APITimeoutError
from rag.llm import DeepSeekLLM
from app import knowledge


class AnswerResilienceTests(unittest.TestCase):
    def test_file_lock_timeout_releases_thread_lock(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(knowledge, 'BACKEND_ROOT', Path(folder)):
            with FileLock(str(Path(folder) / '.knowledge.lock')):
                with self.assertRaises(HTTPException) as raised:
                    with knowledge.knowledge_lock(timeout=0.02):
                        self.fail('file lock must block entry')
                self.assertEqual(raised.exception.status_code, 409)
            with knowledge.knowledge_lock(timeout=0.1):
                pass

    def test_timeout_does_not_retry(self):
        calls = []
        def timeout(request):
            calls.append(request)
            raise httpx.ReadTimeout('simulated timeout', request=request)
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test-only'}):
            llm = DeepSeekLLM()
        self.assertEqual(llm.client.timeout.read, 60)
        self.assertEqual(llm.client.max_retries, 0)
        llm.client._client.close()
        llm.client._client = httpx.Client(transport=httpx.MockTransport(timeout))
        try:
            with self.assertRaises(APITimeoutError):
                llm.generate('test')
            self.assertEqual(len(calls), 1)
        finally:
            llm.client.close()

    def test_empty_answer_is_not_success(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test-only'}):
            llm = DeepSeekLLM()
        try:
            with patch.object(llm.client.chat.completions, 'create') as create:
                create.return_value.choices[0].message.content = '  '
                with self.assertRaises(RuntimeError):
                    llm.generate('test')
        finally:
            llm.client.close()

    def test_thread_lock_contention_and_release(self):
        ready, release = threading.Event(), threading.Event()
        def hold():
            with knowledge._thread_lock:
                ready.set()
                release.wait(5)
        worker = threading.Thread(target=hold)
        worker.start()
        try:
            self.assertTrue(ready.wait(2))
            with self.assertRaises(HTTPException) as raised:
                with knowledge.knowledge_lock(timeout=0.02):
                    self.fail('must not enter while another thread holds the lock')
            self.assertEqual(raised.exception.status_code, 409)
        finally:
            release.set()
            worker.join(2)
        with tempfile.TemporaryDirectory() as folder, patch.object(knowledge, 'BACKEND_ROOT', Path(folder)):
            with self.assertRaises(ValueError):
                with knowledge.knowledge_lock(timeout=0.1):
                    raise ValueError('body failure')
            with knowledge.knowledge_lock(timeout=0.1):
                pass


if __name__ == '__main__':
    unittest.main()
