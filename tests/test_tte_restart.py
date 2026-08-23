#!/usr/bin/env python3
"""TTE crash backoff policy (shared with gnome-ascii-saver helpers)."""

from __future__ import annotations

import unittest

from helpers import (
    TTE_MAX_FAILURES,
    TTE_SUCCESS_RESTART_MS,
    tte_exit_ok,
    tte_failure_delay_ms,
    tte_restart_after,
)


class TteRestartTests(unittest.TestCase):
    def test_successful_wait_status(self) -> None:
        self.assertTrue(tte_exit_ok(0))
        self.assertFalse(tte_exit_ok(1 << 8))

    def test_signaled_status_is_a_failure(self) -> None:
        self.assertFalse(tte_exit_ok(15))

    def test_successful_effect_restarts_immediately_and_resets(self) -> None:
        delay, failures = tte_restart_after(0, 4)
        self.assertEqual(delay, TTE_SUCCESS_RESTART_MS)
        self.assertEqual(failures, 0)

    def test_waitpid_exit_one_is_a_failure(self) -> None:
        result = tte_restart_after(1 << 8, 0)
        self.assertIsNotNone(result)
        delay, failures = result
        self.assertEqual(delay, TTE_SUCCESS_RESTART_MS)
        self.assertEqual(failures, 1)

    def test_exponential_backoff_then_give_up(self) -> None:
        self.assertEqual(tte_failure_delay_ms(1), 80)
        self.assertEqual(tte_failure_delay_ms(2), 160)
        self.assertEqual(tte_failure_delay_ms(3), 320)
        self.assertEqual(tte_failure_delay_ms(4), 640)
        self.assertIsNone(tte_failure_delay_ms(5))
        self.assertIsNone(tte_failure_delay_ms(6))
        self.assertEqual(TTE_MAX_FAILURES, 5)

    def test_failures_backoff_then_give_up(self) -> None:
        failures = 0
        delays = []
        for _ in range(TTE_MAX_FAILURES - 1):
            result = tte_restart_after(1 << 8, failures)
            self.assertIsNotNone(result)
            delay, failures = result
            delays.append(delay)
        self.assertEqual(delays, [80, 160, 320, 640])
        self.assertIsNone(tte_restart_after(1 << 8, failures))

    def test_backoff_rejects_non_positive_counts(self) -> None:
        with self.assertRaises(ValueError):
            tte_failure_delay_ms(0)


if __name__ == "__main__":
    unittest.main()
