#!/usr/bin/env python3
"""Renderer-side KScreenLocker handoff tests."""

from __future__ import annotations

import unittest
from unittest import mock

import app


class _Parameters:
    def __init__(self, active: bool):
        self.active = active

    def unpack(self):
        return (self.active,)


class ScreenLockSignalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = app.SaverApplication(windowed=False, once=False)

    def test_subscribes_to_both_lock_signals_before_querying_state(self) -> None:
        bus = mock.Mock()
        bus.signal_subscribe.side_effect = [11, 12]
        with mock.patch("app.Gio.bus_get_sync", return_value=bus), mock.patch.object(
            self.application, "hold"
        ) as hold:
            self.assertTrue(self.application._watch_screen_lock())

        subscriptions = bus.signal_subscribe.call_args_list
        self.assertEqual(subscriptions[0].args[2], "AboutToLock")
        self.assertEqual(subscriptions[0].args[3], "/ScreenSaver")
        self.assertEqual(subscriptions[1].args[2], "ActiveChanged")
        self.assertEqual(subscriptions[1].args[3], "/ScreenSaver")
        bus.call.assert_called_once()
        self.assertEqual(bus.call.call_args.args[3], "GetActive")
        self.assertEqual(self.application._screen_lock_subscriptions, [11, 12])
        self.assertTrue(self.application._screen_lock_query_pending)
        hold.assert_called_once_with()

    def test_about_to_lock_always_quits_renderer(self) -> None:
        with mock.patch.object(self.application, "quit_saver") as quit_saver:
            self.application._on_about_to_lock()
        quit_saver.assert_called_once_with()

    def test_active_changed_true_quits_renderer(self) -> None:
        with mock.patch.object(self.application, "quit_saver") as quit_saver:
            self.application._on_active_changed(
                None, None, None, None, None, _Parameters(True), None
            )
        quit_saver.assert_called_once_with()

    def test_active_changed_false_keeps_renderer_running(self) -> None:
        with mock.patch.object(self.application, "quit_saver") as quit_saver:
            self.application._on_active_changed(
                None, None, None, None, None, _Parameters(False), None
            )
        quit_saver.assert_not_called()

    def test_initial_active_state_quits_renderer(self) -> None:
        connection = mock.Mock()
        connection.call_finish.return_value = _Parameters(True)
        with mock.patch.object(self.application, "quit_saver") as quit_saver:
            self.application._on_get_active_finished(connection, object(), None)
        quit_saver.assert_called_once_with()

    def test_initial_inactive_state_keeps_renderer_running(self) -> None:
        connection = mock.Mock()
        connection.call_finish.return_value = _Parameters(False)
        self.application._screen_lock_query_pending = True
        with mock.patch.object(self.application, "quit_saver") as quit_saver, mock.patch.object(
            self.application, "activate"
        ) as activate, mock.patch.object(self.application, "release") as release:
            self.application._on_get_active_finished(connection, object(), None)
        quit_saver.assert_not_called()
        self.assertTrue(self.application._screen_lock_ready)
        activate.assert_called_once_with()
        release.assert_called_once_with()

    def test_windows_wait_for_initial_lock_state(self) -> None:
        with mock.patch.object(self.application, "get_windows") as get_windows:
            self.application.do_activate()
        get_windows.assert_not_called()

    def test_initial_query_failure_refuses_to_show(self) -> None:
        connection = mock.Mock()
        connection.call_finish.side_effect = app.GLib.Error("session bus unavailable")
        self.application._screen_lock_query_pending = True
        with mock.patch.object(self.application, "quit") as quit_application, mock.patch(
            "sys.stderr"
        ), mock.patch.object(self.application, "release") as release:
            self.application._on_get_active_finished(connection, object(), None)
        self.assertTrue(self.application.stopping)
        self.assertFalse(self.application._screen_lock_ready)
        quit_application.assert_called_once_with()
        release.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
