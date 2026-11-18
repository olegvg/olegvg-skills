"""Hermetic mobile discovery checks: never start a device, daemon, or test session."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/mobile-test-environments/scripts/inventory.py"


class MobileInventoryTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "The standalone skill needs its discovery helper")
        spec = importlib.util.spec_from_file_location("mobile_inventory", SCRIPT)
        self.mobile = importlib.util.module_from_spec(spec)
        before = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(self.mobile)
        finally:
            sys.dont_write_bytecode = before

    def apple(self, developer, gui=None):
        if gui:
            target = (developer.parent / "Applications/DeviceHub.app" if gui == "Device Hub"
                      else developer / "Applications/Simulator.app")
            target.mkdir(parents=True)
        devices = {"devices": {"com.apple.CoreSimulator.SimRuntime.iOS-27-1": [
            {"udid": "IOS-BOOTED", "name": "Phone A", "state": "Booted", "isAvailable": True},
            {"udid": "IOS-COLD", "name": "Phone B", "state": "Shutdown", "isAvailable": True},
            {"udid": "IOS-MISSING", "name": "Old Phone", "state": "Shutdown", "isAvailable": False},
        ]}}

        def run(argv):
            if argv[-1] == "-p":
                return {"status": "ok", "stdout": str(developer), "stderr": ""}
            return {"status": "ok", "stdout": json.dumps(devices), "stderr": ""}

        with patch.object(self.mobile.shutil, "which", side_effect=lambda name: f"/tools/{name}"), \
             patch.dict(self.mobile.os.environ, {"DEVELOPER_DIR": ""}), \
             patch.object(self.mobile, "run", side_effect=run) as command:
            result = self.mobile.ios_inventory()
        self.assertTrue(all("boot" not in call.args[0] for call in command.call_args_list))
        self.assertEqual(["IOS-BOOTED", "IOS-COLD"], [d["udid"] for d in result["devices"]])
        return result

    def test_device_hub_is_found_in_new_xcode_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            developer = Path(tmp) / "Xcode Alt.app/Contents/Developer"
            developer.mkdir(parents=True)
            result = self.apple(developer, "Device Hub")
            self.assertEqual("Device Hub", result["viewer"]["name"])
            self.assertEqual(str(developer.parent / "Applications/DeviceHub.app"), result["viewer"]["path"])

    def test_legacy_simulator_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            developer = Path(tmp) / "Xcode.app/Contents/Developer"
            developer.mkdir(parents=True)
            self.assertEqual("Simulator", self.apple(developer, "Simulator")["viewer"]["name"])

    def test_devices_are_not_lost_when_no_viewer_app_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            developer = Path(tmp) / "Xcode.app/Contents/Developer"
            developer.mkdir(parents=True)
            result = self.apple(developer)
            self.assertIsNone(result["viewer"])
            self.assertEqual("ok", result["status"])
            self.assertEqual("Booted", result["devices"][0]["state"])

    def test_android_preserves_connected_unauthorized_and_offline_states(self):
        def run(argv):
            output = ("Phone_beta\nTablet_other\n" if "-list-avds" in argv else
                      "List of devices attached\nemulator-5554 device product:test model:Phone\nTEST-USB unauthorized\nemulator-5556 offline\n")
            return {"status": "ok", "stdout": output, "stderr": ""}
        with patch.object(self.mobile, "android_tool", side_effect=lambda name: f"/sdk/{name}"), \
             patch.object(self.mobile, "adb_listening", return_value=(True, "127.0.0.1:5037")), \
             patch.object(self.mobile, "run", side_effect=run) as command, \
             patch.object(self.mobile, "adb_devices", return_value={"status": "ok", "stdout": "emulator-5554 device product:test model:Phone\nTEST-USB unauthorized\nemulator-5556 offline\n", "stderr": ""}):
            result = self.mobile.android_inventory()
        self.assertEqual(["Phone_beta", "Tablet_other"], result["avds"])
        self.assertEqual(["device", "unauthorized", "offline"], [d["state"] for d in result["devices"]])
        self.assertEqual([["/sdk/emulator", "-list-avds"]], [call.args[0] for call in command.call_args_list])

    def test_inventory_does_not_start_an_absent_adb_server(self):
        with patch.object(self.mobile, "android_tool", side_effect=lambda name: f"/sdk/{name}"), \
             patch.object(self.mobile, "adb_listening", return_value=(False, "not listening")), \
             patch.object(self.mobile, "run", return_value={"status": "ok", "stdout": "Phone_beta\n", "stderr": ""}) as command:
            result = self.mobile.android_inventory()
        self.assertEqual("not-running", result["adb"]["status"])
        self.assertEqual([], result["devices"])
        self.assertEqual([["/sdk/emulator", "-list-avds"]], [call.args[0] for call in command.call_args_list])

    def test_custom_adb_endpoint_is_not_silently_replaced(self):
        with patch.dict(self.mobile.os.environ, {"ADB_SERVER_SOCKET": "tcp:remote.example.invalid:9999"}), \
             patch.object(self.mobile.socket, "create_connection") as connect:
            listening, detail = self.mobile.adb_listening()
        self.assertFalse(listening)
        self.assertIn("ADB_SERVER_SOCKET", detail)
        connect.assert_not_called()

    def test_denied_adb_probe_is_an_error_not_an_empty_running_state(self):
        with patch.object(self.mobile, "android_tool", side_effect=lambda name: "/sdk/adb" if name == "adb" else None), \
             patch.dict(self.mobile.os.environ, {"ADB_SERVER_SOCKET": "", "ANDROID_ADB_SERVER_PORT": "5037"}), \
             patch.object(self.mobile.socket, "create_connection", side_effect=PermissionError("sandbox denied")):
            result = self.mobile.android_inventory()
        self.assertEqual("error", result["adb"]["status"])
        self.assertIn("denied", result["adb"]["diagnostic"])

    def test_missing_android_tools_do_not_trigger_installation(self):
        with patch.object(self.mobile, "android_tool", return_value=None), \
             patch.object(self.mobile, "run") as command:
            result = self.mobile.android_inventory()
        self.assertEqual("unavailable", result["status"])
        command.assert_not_called()

    def test_adb_host_query_handles_partial_reads_without_running_adb(self):
        data = b"emulator-5560\tdevice model:Other\n"
        packet = bytearray(b"OKAY" + f"{len(data):04x}".encode() + data)
        class Stream:
            sent = b""
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def sendall(self, payload): self.sent += payload
            def settimeout(self, timeout): pass
            def recv(self, length):
                size = min(length, 2, len(packet))
                result = bytes(packet[:size]); del packet[:size]
                return result
        stream = Stream()
        with patch.object(self.mobile.socket, "create_connection", return_value=stream), \
             patch.object(self.mobile.subprocess, "run") as process:
            result = self.mobile.adb_devices("127.0.0.1:5037")
        self.assertEqual(b"000ehost:devices-l", stream.sent)
        self.assertEqual("ok", result["status"])
        self.assertEqual(data.decode(), result["stdout"])
        process.assert_not_called()

    def test_adb_disappearing_after_probe_does_not_start_a_replacement(self):
        with patch.object(self.mobile, "android_tool", side_effect=lambda name: "/sdk/adb" if name == "adb" else None), \
             patch.object(self.mobile, "adb_listening", return_value=(True, "127.0.0.1:5037")), \
             patch.object(self.mobile.socket, "create_connection", side_effect=ConnectionRefusedError("closed")), \
             patch.object(self.mobile.subprocess, "run") as process:
            result = self.mobile.android_inventory()
        self.assertEqual("error", result["adb"]["status"])
        process.assert_not_called()

    def test_timeout_is_reported_without_becoming_an_empty_device_list(self):
        with patch.object(self.mobile.subprocess, "run", side_effect=subprocess.TimeoutExpired(["xcrun"], 8)):
            result = self.mobile.run(["xcrun", "simctl", "list", "devices", "available", "--json"])
        self.assertEqual("timeout", result["status"])
        self.assertIn("8", result["stderr"])

    def test_broken_simctl_is_distinct_from_no_installed_devices(self):
        def run(argv):
            return ({"status": "ok", "stdout": "/missing/Xcode.app/Contents/Developer", "stderr": ""}
                    if argv[-1] == "-p" else
                    {"status": "error", "stdout": "", "stderr": "Xcode setup is incomplete"})
        with patch.object(self.mobile.shutil, "which", side_effect=lambda name: f"/tools/{name}"), \
             patch.dict(self.mobile.os.environ, {"DEVELOPER_DIR": ""}), \
             patch.object(self.mobile, "run", side_effect=run):
            result = self.mobile.ios_inventory()
        self.assertEqual("error", result["status"])
        self.assertIn("incomplete", result["diagnostic"])


if __name__ == "__main__":
    unittest.main()
