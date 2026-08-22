#!/usr/bin/env python3
"""TTE crash backoff policy (shared conceptually with gnome-ascii-saver)."""

from __future__ import annotations

import unittest

from app import TTE_BACKOFF_CAP_MS, TTE_MAX_FAILURES, TTE_RESTART_MS, tte_restart_after


class TteRestartTests(unittest.TestCase):
    def test_successful_effect_restarts_immediately_and_resets(self) -> None:
        delay, failures = tte_restart_after(0, 4)
        self.assertEqual(delay, TTE_RESTART_MS)
        self.assertEqual(failures, 0)

    def test_failures_backoff_then_give_up(self) -> None:
        failures = 0
        delays = []
        for _ in range(TTE_MAX_FAILURES - 1):
            result = tte_restart_after(1, failures)
            self.assertIsNotNone(result)
            delay, failures = result
            delays.append(delay)
        self.assertEqual(delays[0], TTE_RESTART_MS)
        self.assertEqual(delays[1], TTE_RESTART_MS * 2)
        self.assertLessEqual(delays[-1], TTE_BACKOFF_CAP_MS)
        self.assertIsNone(tte_restart_after(1, failures))


if __name__ == "__main__":
    unittest.main()
