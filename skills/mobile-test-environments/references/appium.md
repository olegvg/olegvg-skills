# Appium CLI and sessions

## Prepare the selected platform

Prefer the project's installed Appium client and existing server. Inspect `appium --version`, `appium driver list --installed`, and `appium driver doctor uiautomator2` or `xcuitest` only when this route is needed. Driver commands may require access to the existing Appium home even for listing; an access error does not prove a missing driver. Do not create a fresh Appium home or install/upgrade drivers as an automatic workaround.

Android uses UiAutomator2; iOS uses XCUITest. Browser-only tests usually belong to the project's Playwright suite, with actual OS/keyboard behavior checked on the chosen device where required.

Use existing SDK/JDK/Xcode installations. Resolve their real locations, for example macOS `/usr/libexec/java_home` and the selected Xcode directory. Pass required `ANDROID_HOME`, `JAVA_HOME` or `DEVELOPER_DIR` to the current process only; preserve unrelated shell configuration and package-manager versions. Diagnose an incompatible runtime explicitly. A doctor's optional video/streaming dependencies do not automatically justify installations.

## Server and session ownership

Check the exact requested server's `/status` and current owner before reuse. If a new local server is needed, choose an unused port and start `appium server --address 127.0.0.1 --port "$APPIUM_PORT" --use-drivers "$DRIVER_NAME" --log "$APPIUM_LOG"` in a managed process session. Wait for its `/status` response with a deadline and record the process identity. Use the configured base path if the existing server has one.

Do not use `--session-override`, `--relaxed-security` or broad insecure features as defaults. A busy port is not permission to terminate its process. An unresponsive server is not permission to create a duplicate server against the same device.

Use a project's WebDriver client, or Appium's documented HTTP API when no client is available. Session capabilities must identify the chosen platform, automation driver and **exact UDID/serial**. Supply the actual app/browser target. Use `appium:noReset: true` to preserve state unless reset/reinstall is part of the approved test. Web-context Chrome may require a compatible Chromedriver; do not disable version checks or auto-download it to conceal a mismatch.

Record the returned session ID. If creation times out with an unknown result, inspect this server and logs before retrying: repeated POSTs can create competing sessions. Delete only a known task-owned session at `/session/<session-id>`; then stop a task-owned server only after checking it has no other users. Do not stop existing sessions as cleanup.

For physical iPhones, WDA needs a valid signing/provisioning setup and the documented device preparation. Appium can invoke `xcodebuild` without an open Xcode editor. No account, trust, permission or signing changes are implied by a simulator smoke-test request.

## Interaction and evidence

Prefer fresh semantic selectors. Native Chrome accessibility elements may be recreated after opening a modal, changing focus, typing or showing the keyboard. On a stale-element failure, observe the current hierarchy and re-find the target before a bounded retry. Do not cache element IDs across those transitions. If coordinates are necessary, derive them from freshly observed bounds; avoid saved screen coordinates and arbitrary sleeps.

Respect operation semantics: retrying a read/lookup is different from appending text or repeating a confirm action. Verify the current value before repeating a non-idempotent action. For keyboard tests, use the normal IME and establish visibility plus viewport/scroll behavior; a text-injection API alone is not keyboard proof.

Save screenshots and useful bounded diagnostics to the task's artifact directory; report paths and results. Do not dump base64 screenshots, full hierarchies or device logs into conversation. Use synthetic application data and avoid personal-account screens in evidence.

## Optional viewer

Appium Inspector is optional for CLI tests. Inspector 2026.5.1 and later can
attach manually using a known session ID and exact server address. Use this
option to observe the session without enabling Appium 3 session discovery.
Keep the existing session running and verify app behavior separately.

Sources: [driver list](https://appium.io/docs/en/latest/ecosystem/drivers/), [server requirements](https://appium.io/docs/en/latest/quickstart/requirements/), [XCUITest device setup](https://appium.github.io/appium-xcuitest-driver/latest/getting-started/device-setup/), [WebDriver protocol](https://appium.io/docs/en/latest/reference/api/webdriver/), [Inspector attachment](https://appium.github.io/appium-inspector/latest/session-builder/attach-to-session/).
