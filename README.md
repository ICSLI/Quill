# 🪶 Quill - AI Writing Assistant for Windows

**Quill** is a background AI writing assistant for Windows. Select text, press a hotkey, and choose a writing action or enter a custom instruction. Quill sends the request to your configured OpenAI-compatible API and replaces the selection with the text response.

Inspired by [WritingTools](https://github.com/theJayTea/WritingTools), Quill supports editable ChatML prompts, local model servers, and Windows DPAPI encryption for saved API keys.

## 📥 Download

- [Latest stable release](https://github.com/ICSLI/Quill/releases/latest)
- [Quill v1.0.12 pre-release](https://github.com/ICSLI/Quill/releases/tag/v1.0.12) — includes hidden popup/Settings preloading and local diagnostics. Login-time hotkey verification is still pending, and the reported intermittent failure after a notification sound remains under investigation.

Requirements: **Windows 10/11** and access to a compatible API or running local model server.

The instructions below describe v1.0.12. Older releases may differ.

1. Download the Windows ZIP attached to the chosen release, such as `Quill-v1.0.12-windows.zip`.
2. Extract the entire archive to a writable folder.
3. Run `Quill.exe`. Keep `_internal` beside it; the executable is not a standalone file.

## 🚀 Quick Start

On first launch, enter your **Base URL**, **API Key**, and **Model**. The API key can be empty when your local server does not require authentication. Use a model ID available on your endpoint.

| Provider | Example Base URL | Model |
|----------|------------------|-------|
| [OpenAI](https://developers.openai.com/api/reference/resources/chat) | `https://api.openai.com/v1` | A Chat Completions model available to your API account |
| [Google Gemini](https://ai.google.dev/gemini-api/docs/openai) | `https://generativelanguage.googleapis.com/v1beta/openai/` | A model supported by the provider's OpenAI-compatible endpoint |
| [Ollama](https://docs.ollama.com/api/openai-compatibility) | `http://localhost:11434/v1` | The model ID served by your running local instance |
| [llama.cpp](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) | `http://localhost:8080/v1` | The model ID served by your running local instance |

Enter the API root, not the full `/chat/completions` URL: Quill appends `chat/completions` to the configured path. A provider-specific path is supported; it does not have to end in `/v1`.

Quill uses non-streaming **Chat Completions** and expects text in `choices[0].message.content`. It sends `temperature` with each request. Model and parameter support varies by provider; an OpenAI-compatible endpoint does not guarantee that every model or API feature is supported.

## ✨ Usage

1. Select text in an application that supports `Ctrl+C` and `Ctrl+V`.
2. Press `Ctrl+Space` to open Quill.
3. Choose a quick action, or type a custom instruction and press **Enter** or click **Send**.
4. Keep the source window and selection available until the response is ready.

Before pasting, Quill checks that the source window is in the foreground and the selected text still matches. If those checks fail, it leaves the target untouched and offers the response for manual copying. Empty responses and responses marked as truncated or filtered by the API are rejected.

### Quick Actions

| Action | Default behavior | Default temperature |
|--------|------------------|---------------------|
| Grammar Check | Fix spelling and grammar | 0.3 |
| Rewrite | Improve clarity, readability, and flow | 0.7 |
| Summarize | Condense text to key points | 0.5 |
| Translate | Translate into **English** | 0.3 |

For another target language, submit a custom instruction such as “Translate into Korean,” or edit the Translate template in Settings. A quick action uses its saved template; text in the instruction box affects that action only if its template includes `{{instruction}}`.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Space` | Open the popup for selected text; customizable |
| `Ctrl+Shift+Space` | Quick Repeat; customizable and optional |
| `Enter` or `Ctrl+Enter` | Send while typing in the instruction box |
| `Shift+Enter` | Insert a newline in the instruction box |
| `Esc` | Close the popup |

**Quick Repeat** submits the last action and instruction from the current session against a new selection, without opening the popup. If no action has been submitted in that session, it opens the normal popup. The last action is not restored after restarting Quill.

### System Tray

Right-click the tray icon to open **Settings**, toggle **Pause/Resume**, or **Quit**.

Pause releases Quill's registered shortcuts. Resume attempts to register them again; a conflict leaves Quill paused. Pause applies to the current session. To start a session paused, run `Quill.exe --paused`; a later normal launch starts with shortcuts enabled if registration succeeds.

### First-Open Responsiveness

Since v1.0.12, Quill prepares popup rendering and native window creation while hidden at startup. Settings are preloaded shortly afterward when no text operation or dialog is active. This does not display a window, change focus, save settings, or make an API request.

Opening Settings uses the prepared window. Opening it again while it is visible keeps current edits. After Save or Cancel, Quill prepares a fresh dialog. If optional preloading fails, ordinary window opening remains available.

## ⚙️ Settings and Prompts

Open **Settings** from the system tray:

- **API** — Base URL, API key, model, and Additional Params. Leave the key field empty to keep the saved key; select **Remove saved API key** to remove it.
- **Hotkeys** — Main and Quick Repeat shortcuts. Clear Quick Repeat to disable that shortcut. When Quill is active, changed shortcuts are registered before saving; a conflict keeps the previous settings. Changes saved while paused take effect on Resume.
- **Prompts** — Edit existing prompt names, templates, and temperatures. The Custom prompt's name is fixed. Switching prompts retains drafts; **Cancel** discards them. **Reset to Default** is also a draft until **Save** is clicked.

Settings cannot be changed while a text or AI operation is in progress.

### Additional Parameters

Enter a JSON object containing parameters accepted by your endpoint and model. For example, if supported:

```json
{
  "top_p": 0.9
}
```

These parameters apply to every request. `model`, `messages`, and `stream` cannot be overridden here. Including `temperature` overrides the value from the selected prompt.

### ChatML Templates

Use **Settings > Prompts** to customize a template. For example:

```text
<|im_start|>system
Follow the user's writing instruction. Return only the resulting text.
<|im_end|>
<|im_start|>user
{{instruction}}

Text:
{{text}}
<|im_end|>
```

- `{{text}}` — selected text
- `{{instruction}}` — custom instruction

Quill parses the template's message roles before inserting these values. Saved overrides are kept in `user_prompts.json`; editing the bundled defaults is not required. Adding an arbitrary prompt key to a JSON file does not add a new quick-action button to the popup.

## 📂 Data, Upgrades, and Automatic Startup

| Run mode | Settings and encrypted API key | Prompt overrides |
|----------|--------------------------------|------------------|
| Extracted Windows build | `_internal/data/config.json` | `_internal/data/user_prompts.json` |
| Source checkout | `data/config.json` | `data/user_prompts.json` |

Only the saved API key is DPAPI-encrypted; the other settings and prompt files are JSON. The encrypted key is tied to your Windows user profile. When moving to another account or computer, you may need to enter it again.

### Upgrade an Existing Installation

1. Quit the old Quill instance from its tray menu.
2. Extract the new release into a separate folder.
3. Copy `config.json` and, if present, `user_prompts.json` from the old `_internal/data` folder to the new `_internal/data` folder. Create the destination data folder if needed.
4. Run the new `Quill.exe` and verify settings, prompts, and shortcuts.
5. Update your normal and Startup shortcuts to the new executable before deleting the old folder.

Keep the old folder until the new installation works. Running both copies can cause shortcut conflicts. Do not distribute your data files with a release ZIP.

### Automatic Startup

Quill does not create a Startup shortcut automatically. To enable it:

1. Create a shortcut to the extracted `Quill.exe`.
2. In File Explorer's address bar, open `shell:startup` and place the shortcut there.
3. Set its target to the current executable and its working directory to that executable's folder.
4. Leave arguments empty for a normal active launch. Add `--paused` only if a paused launch is intended.

Keep one Quill shortcut in Startup. After an upgrade, check that it points to the new folder. Launching the shortcut in an existing session does not verify behavior immediately after reboot/sign-in.

## 🔧 Troubleshooting

### Hotkey Does Not Open the Popup

Check that text is selected and that the tray menu offers **Pause**, meaning Quill is active. If it offers **Resume**, Quill is paused.

Windows shortcuts are exclusive. Another application may own the combination; choose another shortcut in Settings, then Resume. Quill uses Windows `RegisterHotKey` through Qt's message loop, without a global keyboard hook or ordinary key-state tracking.

Some applications block synthetic copy/paste or require matching privilege levels. Compare behavior in a normal text editor before changing how Quill is launched.

### API Request Fails

Verify the provider's Base URL, model ID, authentication, quota, and accepted parameters. The Base URL must be HTTP(S) without embedded credentials, query parameters, or fragments. Do not add `/chat/completions` yourself. Remove unsupported Additional Params and check whether the model accepts `temperature`.

### Response Is Not Pasted

The target must support copy/paste. Return to the original window with the original text selected. A failed source-window or selection check blocks automatic replacement; use **Copy Response** in the error dialog to paste manually.

### Failure After a Notification Sound

The reported intermittent symptom is still under investigation. Since v1.0.12, local diagnostics help distinguish shortcut receipt, selection-copy timeout, an AI request, and an open error dialog.

Open `%LOCALAPPDATA%\Quill\logs\events.log`. Records contain fixed event names, counts, flags, and redacted code locations. Selected text, prompts, API responses, and credentials are excluded. Logs rotate at 256 KiB and keep two backups; Quill does not upload them.

Useful events include `hotkey.received`, `selection.copy_timed_out`, `ai.started`, `ai.completed`, `replacement.completed`, `dialog.opened`, and `dialog.closed`. Check for an open Quill dialog before restarting. When reporting a failure, include the Quill version, affected application, failed step, and relevant event sequence.

### Known Limitations

- Clipboard restoration preserves **plain text only**. Previously copied formatting, images, and other formats may be lost from the clipboard; source files are not deleted.
- Settings and prompts are saved to separate files. Abrupt termination between writes can leave only part of a settings change saved.
- Application compatibility, Korean IME, multi-monitor behavior, and login-time shortcuts require manual checks in the target environment. Passing automated tests does not establish compatibility with every application.

## 🛠️ Development

See [Building Quill for Windows](build_instructions.md) for environment setup, running from source, tests, packaging, and release checks.

| Path | Purpose |
|------|---------|
| `main.py` | Entry point, instance lock, and diagnostics setup |
| `app/` | App lifecycle, Windows hotkey registration, clipboard workers, and tray |
| `core/` | API client, ChatML parser, settings, prompts, DPAPI, storage, and diagnostics |
| `ui/` | Onboarding, popup, Settings, hidden-window preparation, and styles |
| `resources/` | Default prompts and icons |
| `tests/` | Core, input, UI, native Windows, and lifecycle regression coverage |
| `build.py` | PyInstaller packaging with the current Python interpreter |

## 🙏 Credits

- [WritingTools](https://github.com/theJayTea/WritingTools) — inspiration
- [PySide6](https://doc.qt.io/qtforpython-6/) — GUI and native message-loop integration
- [pynput](https://github.com/moses-palmer/pynput) — shortcut parsing, cursor position, and synthetic copy/paste input
- [pyperclip](https://github.com/asweigart/pyperclip) — clipboard text access
- [httpx](https://www.python-httpx.org/) — HTTP client

## 📄 License

GNU General Public License, version 3 or later. See [LICENSE](LICENSE).

Copyright (c) 2026 ICSLI.
