---
name: mobile-test-environments
description: Use when starting, inspecting, viewing, troubleshooting or cleaning up Android emulators, iOS simulators, Device Hub or Appium test sessions. Triggers include "mobile test environment", "виртуальный iPhone", "запусти эмулятор", "покажи экран телефона" and "настрой Appium". Excludes app feature implementation and browser-only testing.
---

# Mobile Test Environments

Manage the device and automation environment around an application's tests. Prefer installed CLI tools; Maestro is optional, never a prerequisite. Keep application-specific test logic in its repository.

## Discover, then route

Identify the requested platform, virtual versus physical device, and operation. Run `python3 <skill-dir>/scripts/inventory.py --platform all`, resolving `<skill-dir>` from this file's location. Use `android` or `ios` instead of `all` for a platform-specific request. The helper reports tools, installed virtual devices, running states and the selected Xcode viewer. It does not install tools, boot devices or start an absent ADB server. Missing tools and failed discovery are distinct from an empty device list.

Read only the matching reference; add another when the task crosses that boundary:

| Task | Read |
| --- | --- |
| Android AVDs, ADB, screen viewing, keyboard | [Android](references/android.md) |
| Virtual iPhone, Device Hub/Simulator, physical iPhone viewing | [iOS](references/ios.md) |
| Appium server, drivers, sessions, Inspector or driver errors | [Appium](references/appium.md) |
| Local app/Docker connectivity, test evidence and handoff | [Verification](references/verification.md) |

Installed runtime, booted device, visible screen and passing test are separate facts. Inventory alone proves only the first two when explicitly reported.

## Resource ownership

Use exact Android serials/iOS UDIDs and selected server URLs. Resolve an ambiguous target before changing it. Reuse existing environments without claiming ownership of them.

For each resource created or changed, record its identifier, prior state, task owner, endpoint/process identity and intended cleanup. Coordinate one owner per device/automation session. Before stopping anything, verify that it still matches that record. Leave pre-existing resources running unless their owner/user authorized the exact action; never use global shutdown, kill, erase or Docker teardown as routine cleanup.

Routine startup and tests follow the user's existing scope. Installation/upgrades, data wipes, signing/account changes and personal-device permissions require the corresponding authorization. Do not create a second server, replace a busy port, or reset shared tooling to bypass a diagnostic failure.

## Finish

Report target device/OS, tools used, application revision/URL, actual checks and evidence paths, remaining gaps, and any resources intentionally retained. State whether checks used browser emulation, an OS simulator or a physical phone. Clean up only owned resources requested for teardown.
