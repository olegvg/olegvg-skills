# Application connectivity and verification

## Reach the intended application

Use the application's existing startup/test commands and public synthetic test configuration. Record its source revision, URL, environment and any required test-user context. The skill manages the mobile environment; it does not authorize changing app code, production data, deployment or accounts.

- Android Emulator: `10.0.2.2` refers to the host loopback interface. `127.0.0.1` refers to that emulator itself.
- Inspect `adb -s "$DEVICE_SERIAL" reverse --list` before adding a mapping.
  Use `adb -s "$DEVICE_SERIAL" reverse --no-rebind "tcp:$DEVICE_PORT" "tcp:$HOST_PORT"`
  for an unused port. If it is still the task's mapping at teardown, remove it
  with `adb -s "$DEVICE_SERIAL" reverse --remove "tcp:$DEVICE_PORT"`.
- iOS Simulator can normally reach a Mac-hosted loopback service at its host URL; verify the actual route on the selected simulator. A physical phone needs an explicitly reachable address/forwarding route; do not assume its localhost is the Mac.
- For Docker-hosted apps, inspect the project's existing published ports and readiness endpoint. Reuse its approved stack. Start or stop only scoped services/resources that this task owns; avoid broad compose teardown. A container bridge IP is not a portable host address for a phone.

Keep Appium bound to local loopback unless remote access was explicitly requested. Do not expose automation servers, weaken firewalls or change network/security settings merely to reach a local fixture. Diagnose a bad URL, unavailable service and permission error separately.

## Prove the requested behavior

Choose a small meaningful flow in the real app or a clearly synthetic fixture. Baseline viewport emulation is useful for layout, but does not prove native keyboards, safe areas, iOS Safari or device permissions.

For an interactive mobile flow, relevant checks can include entering an asymmetric/long draft, opening an overlay, returning focus after a child closes, verifying keyboard-visible actions, and checking retained values after an allowed presentation change. Use only the checks required by the app/task. A boot, screenshot, doctor pass or mocked callback is not an end-to-end test.

Observe the final screen and state. Keep screenshots at useful states, including the visible keyboard when that is the acceptance boundary. Distinguish a hidden screen running headlessly from an open viewer. Record unsupported operations and failed checks honestly; do not relabel text injection as a real keyboard, a simulator as a physical phone, or native setup as functional coverage.

## Receipt and teardown

Extend the project's existing test report/checklist rather than adding a second tracker. Record:

- Platform, virtual/physical model, OS and exact device identifier.
- Appium/driver or other test tool, app revision/URL and any relevant fixture configuration.
- Commands/scenarios and their actual pass/fail/skip results; screenshots/log paths and limitations.
- Device prior state and task-owned process/session/mapping identifiers; what was stopped or intentionally retained and why.

Before teardown, recheck resource identity and current use. End an owned automation session before stopping its owned device/server. Restore only settings changed by this task when restoration is appropriate for that same test device; preserve unrelated accounts, IMEs, simulators, ADB services and Docker projects.

Sources: [Android network addresses](https://developer.android.com/studio/run/emulator-networking-address), [ADB forwarding](https://developer.android.com/tools/adb), [Playwright device emulation](https://playwright.dev/docs/emulation).
