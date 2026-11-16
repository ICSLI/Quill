# Building Quill for Windows

## Environment and Source Run

Use Windows 10/11, Python 3.10 or newer, and a dedicated virtual environment. The v1.0.12 Windows build was packaged with Python 3.13.5.

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Source runs use `data/config.json` and `data/user_prompts.json`. A packaged build uses `_internal/data` beside its bundled modules. See [Data, Upgrades, and Automatic Startup](README.md#-data-upgrades-and-automatic-startup) for migration and shortcut setup.

## Automated Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite covers API response handling with fake responses, clipboard/input doubles, settings transactions, prompt drafts, worker cleanup, and native Windows shortcut registration. Hidden-window tests exercise Windows rendering without displaying or activating the prepared windows. Lifecycle tests cover Settings preloading, Save/Cancel, and fallback after an injected rendering failure.

Automated tests do not spend API credits or send keystrokes to other applications. Native Windows cases require Windows; DPAPI round-trip coverage requires access to the current Windows user profile and can be skipped in a restricted sandbox. Check the result for skips when recording verification. These checks do not replace real application, IME, or reboot/sign-in testing.

## Build the Portable Application

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe build.py
```

`build.py` uses its own Python interpreter and resolves project inputs relative to the script, so it can be invoked from another working directory. It does not install dependencies automatically or delete the entire build/dist trees. PyInstaller replaces **`dist/Quill`** when rebuilding; preserve any user data in that output before running a build.

Distribute the **entire `dist/Quill` folder**, including `_internal`. `Quill.exe` is not a standalone executable. Qt's PyInstaller hooks collect the imported GUI modules; unrelated scientific packages are excluded. DPAPI uses Python's standard library and the Windows API.

Before creating `Quill-v<version>-windows.zip`, confirm that the output contains no runtime `data` folder, `config.json`, `user_prompts.json`, lock files, or local diagnostic logs. ZIP the contents of `dist/Quill` so `Quill.exe` and `_internal` are together at the archive root. Extract that ZIP to a fresh folder for verification.

## Manual Release Checks

Record which checks were completed and which remain pending. Mark a candidate as a pre-release when required manual checks remain incomplete, and describe the pending verification and known issues in its release notes.

- Complete onboarding from a fresh extraction and restart to check persistence.
- Open the popup and use Quick Repeat, including overlapping shortcut combinations and repeated identical selections.
- Test a shortcut conflict: Quill should stay paused with Settings available. Change the shortcut and Resume.
- Test Pause/Resume and shortcut changes while paused; verify quitting releases registrations.
- Check that startup prepares popup and Settings without displaying either window or changing focus.
- Open Settings again while it is visible; edits should remain. Cancel, reopen, and verify discarded edits are absent. Save, reopen, and verify saved values are present.
- Inject a preload failure during development; ordinary popup and Settings opening should remain available.
- Select text in Notepad and a browser, then run an action against a configured API.
- Change the foreground window or selected text before the response is applied: the source checks should block replacement and make the response available for manual copying.
- Test Korean IME, multiline text, and multi-monitor/taskbar placement.
- Check timeout/authentication failures and confirm a later request can be attempted.
- Quit during a request and confirm that the process exits cleanly and releases its shortcuts.
- Launch through the Startup shortcut and verify shortcut registration.
- Reboot or sign out/in, then test `Ctrl+Space` immediately after login. Launching a shortcut in an existing session does not replace this check.

## Diagnostics and Publishing

Since v1.0.12, `%LOCALAPPDATA%\Quill\logs\events.log` records local operation stages and redacted code locations. See [Troubleshooting](README.md#-troubleshooting) for log scope and known limitations. Logs and user data do not belong in the public ZIP.

Compare the source commit, tag, release text, uploaded ZIP checksum, and installed files before declaring a release complete. Use the existing English imperative commit style and release sections: Bug Fixes, Improvements, Known Limitations, Download, and Requirements. List unresolved issues explicitly; automated results alone do not establish that an intermittent failure is fixed.

Documentation-only follow-up commits do not require replacing a published executable or moving an existing version tag. Keep the release tag and ZIP tied to the source used to build that version.
