# Building Quill for Windows

Use Python 3.10 or newer and a dedicated virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m unittest discover -s tests -v
python build.py
```

The build uses the current Python interpreter and works from any working directory.
It does not install dependencies automatically or delete the entire build/dist trees.
PyInstaller replaces `dist/Quill` when rebuilding, so keep user data outside that output before rebuilding.

Distribute the **entire `dist/Quill` folder**, including `_internal`, as a ZIP.
`dist/Quill/Quill.exe` is not a standalone executable.
Qt's PyInstaller hooks collect the imported GUI modules; unrelated scientific packages are excluded.
DPAPI encryption uses the Windows API through Python's standard library.

Before distributing a release, check:

- Launch from a fresh extracted directory, complete onboarding, and restart.
- Test popup and quick-repeat hotkeys, including overlapping key combinations.
- Select text in Notepad and a browser, then run an action against a configured API.
- Change focus or selection while waiting: the original text must remain untouched.
- Test Korean IME, multiline text, repeated identical selections, and multi-monitor taskbars.
- Check timeout/authentication failures and settings persistence after a restart.
- Quit during a request and verify that no background process remains.

Automated tests use fake API responses and clipboard/input doubles. They do not spend API credits or send keystrokes to other applications. DPAPI's real round-trip test requires access to the current Windows user profile and can be skipped in a restricted sandbox.
