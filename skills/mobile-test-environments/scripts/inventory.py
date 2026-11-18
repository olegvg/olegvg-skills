#!/usr/bin/env python3
"""Discover local mobile tools and device state without booting or resetting devices."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time


def run(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
        return {"status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout.strip(), "stderr": result.stderr.strip()[:400]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "stdout": "", "stderr": "Discovery exceeded 8 seconds"}
    except OSError as exc:
        return {"status": "error", "stdout": "", "stderr": str(exc)[:400]}


def android_tool(name):
    found = shutil.which(name)
    if found:
        return found
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             str(Path.home() / "Library/Android/sdk"), str(Path.home() / "Android/Sdk")]
    directory = "platform-tools" if name == "adb" else "emulator"
    for root in roots:
        path = Path(root) / directory / name if root else None
        if path and path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def adb_listening():
    # Do not start a daemon or accidentally query the wrong configured endpoint.
    if os.environ.get("ADB_SERVER_SOCKET"):
        return None, "ADB_SERVER_SOCKET is configured; inspect that endpoint explicitly"
    try:
        port = int(os.environ.get("ANDROID_ADB_SERVER_PORT", "5037"))
        if not 1 <= port <= 65535:
            raise ValueError("invalid port")
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True, f"127.0.0.1:{port}"
    except ConnectionRefusedError:
        return False, "Local ADB server is not listening; not started"
    except (OSError, ValueError) as exc:
        return None, f"Cannot inspect local ADB endpoint: {exc}"


def adb_devices(endpoint):
    # Query the documented host service directly: the adb CLI can auto-start a
    # replacement daemon if the server disappears after the readiness probe.
    host, port = endpoint.rsplit(":", 1)
    try:
        with socket.create_connection((host, int(port)), timeout=2) as stream:
            deadline = time.monotonic() + 3
            def receive(length):
                result = bytearray()
                while len(result) < length:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("ADB inventory exceeded 3 seconds")
                    stream.settimeout(remaining)
                    chunk = stream.recv(length - len(result))
                    if not chunk:
                        raise ValueError("ADB inventory connection closed early")
                    result.extend(chunk)
                return bytes(result)
            service = b"host:devices-l"
            stream.sendall(f"{len(service):04x}".encode() + service)
            status = receive(4)
            if status not in (b"OKAY", b"FAIL"):
                raise ValueError("Unexpected ADB response")
            length = int(receive(4), 16)
            output = receive(length).decode("utf-8", errors="replace")
            return {"status": "ok" if status == b"OKAY" else "error",
                    "stdout": output if status == b"OKAY" else "",
                    "stderr": output[:400] if status == b"FAIL" else ""}
    except (OSError, ValueError) as exc:
        return {"status": "error", "stdout": "", "stderr": str(exc)[:400]}


def android_inventory():
    adb, emulator = android_tool("adb"), android_tool("emulator")
    result = {"status": "ok" if adb or emulator else "unavailable",
              "tools": {"adb": adb, "emulator": emulator}, "avds": [], "devices": []}
    if emulator:
        avds = run([emulator, "-list-avds"])
        result["avd_status"] = avds["status"]
        if avds["status"] == "ok":
            result["avds"] = [line for line in avds["stdout"].splitlines() if line.strip()]
        else:
            result["diagnostic"] = avds["stderr"]
    if not adb:
        result["adb"] = {"status": "unavailable"}
        return result
    listening, detail = adb_listening()
    if not listening:
        result["adb"] = {"status": "not-queried" if os.environ.get("ADB_SERVER_SOCKET") else ("error" if listening is None else "not-running"), "diagnostic": detail}
        return result
    devices = adb_devices(detail)
    result["adb"] = {"status": devices["status"], "endpoint": detail}
    if devices["status"] != "ok":
        result["adb"]["diagnostic"] = devices["stderr"]
        return result
    for line in devices["stdout"].splitlines():
        parts = line.split()
        if not parts or line.startswith("List of devices") or line.startswith("*"):
            continue
        if len(parts) >= 2:
            result["devices"].append({"serial": parts[0], "state": parts[1]})
    return result


def ios_inventory():
    xcrun = shutil.which("xcrun")
    if not xcrun:
        return {"status": "unavailable", "diagnostic": "xcrun is not on PATH", "devices": [], "viewer": None}
    selected = os.environ.get("DEVELOPER_DIR")
    if not selected:
        selector = shutil.which("xcode-select")
        selection = run([selector, "-p"]) if selector else {"status": "error", "stdout": "", "stderr": "xcode-select missing"}
        if selection["status"] != "ok":
            return {"status": selection["status"], "diagnostic": selection["stderr"], "devices": [], "viewer": None}
        selected = selection["stdout"]
    developer = Path(selected).expanduser()
    if developer.suffix == ".app":
        developer = developer / "Contents/Developer"
    result = {"status": "ok", "developer_dir": str(developer), "viewer": None, "devices": []}
    candidates = [("Device Hub", developer.parent / "Applications/DeviceHub.app"),
                  ("Simulator", developer / "Applications/Simulator.app"),
                  ("Simulator", developer.parent / "Applications/Simulator.app")]
    for name, app in candidates:
        if app.is_dir():
            result["viewer"] = {"name": name, "path": str(app)}
            break
    listing = run([xcrun, "simctl", "list", "devices", "available", "--json"])
    if listing["status"] != "ok":
        result.update(status=listing["status"], diagnostic=listing["stderr"])
        return result
    try:
        groups = json.loads(listing["stdout"])["devices"]
        if not isinstance(groups, dict):
            raise ValueError("devices must be an object")
        for runtime, devices in groups.items():
            if not isinstance(devices, list):
                raise ValueError("runtime devices must be an array")
            for device in devices:
                if not isinstance(device, dict):
                    raise ValueError("device must be an object")
                if device.get("isAvailable") is False:
                    continue
                if not all(isinstance(device.get(key), str) and device[key] for key in ("udid", "name", "state")):
                    raise ValueError("device identity/state is missing")
                result["devices"].append({key: device[key] for key in ("udid", "name", "state")} | {"runtime": runtime})
    except (ValueError, KeyError, TypeError) as exc:
        result.update(status="error", diagnostic=f"Invalid simctl inventory: {exc}", devices=[])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("android", "ios", "all"), default="all")
    args = parser.parse_args()
    result = {"tools": {name: shutil.which(name) for name in ("appium", "scrcpy", "xcrun", "java")}}
    if args.platform in ("android", "all"):
        result["android"] = android_inventory()
    if args.platform in ("ios", "all"):
        result["ios"] = ios_inventory()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
