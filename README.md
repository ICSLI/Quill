# 🪶 Quill - AI Writing Assistant for Windows

**Quill** is a lightweight, background AI writing assistant for Windows. Select any text, press a hotkey, and let AI transform your writing instantly.

Inspired by [WritingTools](https://github.com/theJayTea/WritingTools), Quill offers deeper customization with ChatML prompt support and works with any OpenAI-compatible API.

## ✨ What is Quill?

Quill runs quietly in your system tray, ready to help whenever you need it. Whether you're writing emails, coding, or drafting documents, Quill can:

- **Fix grammar and spelling** - Clean up your text instantly
- **Rewrite content** - Make your writing clearer and more engaging
- **Summarize text** - Get the key points from long content
- **Translate** - Convert text to different languages
- **Custom instructions** - Tell the AI exactly what you want

**How it works:**
1. Select any text in any application
2. Press the hotkey (default: `Ctrl+Space`)
3. Choose a quick action or type custom instructions
4. Your selected text is automatically replaced with the AI response

## 🚀 Features

- **OAI Compatible API** - Works with OpenAI, Google Gemini, Ollama, llama.cpp, KoboldCPP, and more
- **ChatML Prompt Format** - Advanced prompt customization with `<|im_start|>` tags
- **Windows DPAPI Encryption** - Your API key is securely encrypted and bound to your Windows account
- **Global Hotkey** - Works in any application
- **Quick Repeat** - Instantly repeat last action with a single hotkey
- **System Tray** - Runs quietly in the background
- **Dark Theme** - Easy on the eyes

## 📥 Download

Download the latest release from [GitHub Releases](../../releases).

1. Download `Quill.zip` from the latest release
2. Extract to any folder
3. Run `Quill.exe`

## ⚡ Quick Start

### First Run Setup

On first launch, you'll see the onboarding window:

1. **Base URL** - Enter your API endpoint
2. **API Key** - Enter your API key (stored encrypted)
3. **Model** - Enter the model name

### API Configuration Examples

| Provider | Base URL | Model |
|----------|----------|-------|
| OpenAI | `https://api.openai.com/v1` | `gpt-5.1-2025-11-13` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` |
| Ollama | `http://localhost:11434/v1` | `gemma3` |
| llama.cpp | `http://localhost:8080/v1` | (your loaded model) |

## 📖 Usage

### Basic Workflow

1. **Select text** in any application
2. **Press hotkey** (default: `Ctrl+Space`)
3. **Choose action:**
   - Click a quick action button (Grammar, Rewrite, Summarize, Translate)
   - Or type custom instructions and press `Ctrl+Enter`
4. **Done!** Selected text is replaced with AI response

### Quick Actions

| Action | Description | Temperature |
|--------|-------------|-------------|
| Grammar Check | Fix spelling and grammar errors | 0.3 |
| Rewrite | Make text clearer and more engaging | 0.7 |
| Summarize | Condense to key points | 0.5 |
| Translate | Translate to another language (specify in instruction) | 0.3 |

### ⌨️ Keyboard Shortcuts

- `Ctrl+Space` - Open Quill popup (customizable)
- `Ctrl+Shift+Space` - Quick Repeat: repeat last action without popup (customizable)
- `Ctrl+Enter` - Send custom instruction
- `Esc` - Close popup

### System Tray Menu

Right-click the tray icon for options:
- **Settings** - Configure API, hotkey, and prompts
- **Pause/Resume** - Temporarily disable hotkey
- **Quit** - Exit Quill

## 📁 Project Structure

```
Quill/
├── main.py                    # Entry point
├── build.py                   # PyInstaller build script
├── requirements.txt           # Dependencies
│
├── app/                       # Application logic
│   ├── application.py         # Main QuillApp class
│   ├── hotkey_manager.py      # Global hotkey handling
│   ├── text_processor.py      # Text extraction/replacement
│   └── tray_manager.py        # System tray icon
│
├── core/                      # Core modules
│   ├── ai_provider.py         # OAI Compatible API client
│   ├── config_manager.py      # Settings management
│   ├── crypto_manager.py      # Windows DPAPI encryption
│   ├── prompt_manager.py      # Prompt templates
│   ├── chatml_parser.py       # ChatML format parser
│   └── single_instance.py     # Prevent multiple instances
│
├── ui/                        # User interface
│   ├── styles.py              # Dark theme styles
│   ├── onboarding_window.py   # First-run setup
│   ├── settings_window.py     # Settings dialog
│   └── popup_window.py        # Main interaction popup
│
├── resources/                 # Assets
│   ├── default_prompts.json   # Default prompt templates
│   └── icon.ico               # Application icon
│
└── data/                      # User data (not in repo)
    └── config.json            # User configuration
```

## ⚙️ Configuration

### Settings Window

Access via system tray → Settings:

- **API Tab**
  - Base URL - API endpoint
  - API Key - Encrypted storage
  - Model - Model name
  - Additional Params - Extra API parameters (JSON)

- **Hotkey Tab**
  - Main Hotkey - Opens popup for action selection
  - Quick Repeat - Repeats last action without popup (optional)

- **Prompts Tab**
  - Edit prompt names and temperatures

### Additional Parameters

You can pass extra parameters to the API:

```json
{
  "reasoning_effort": "low",
  "top_p": 0.9
}
```

## 🎨 Custom Prompts (ChatML)

Edit `resources/default_prompts.json` to customize prompts:

```json
{
  "my_prompt": {
    "name": "My Custom Prompt",
    "template": "<|im_start|>system\nYou are a helpful assistant.\n<|im_end|>\n<|im_start|>user\n{{instruction}}\n\nText:\n{{text}}\n<|im_end|}",
    "temperature": 0.7
  }
}
```

### Template Variables

- `{{text}}` - The selected text
- `{{instruction}}` - User's custom instruction

## 🔧 Troubleshooting

### Hotkey not working

1. Another app may be using the same hotkey - change in Settings
2. Try running Quill as administrator (required for some apps)
3. Check if Quill is paused (tray menu)

### API errors

1. Verify Base URL ends with `/v1` for OpenAI-compatible APIs
2. Check API key is correct
3. Ensure your API has sufficient credits/quota

### Text not replaced

1. Make sure text is actually selected
2. Target app must support `Ctrl+V` paste
3. Some apps (password managers) block clipboard access

## 🛠️ Building from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Run directly
python main.py

# Build executable
python build.py
```

## 🙏 Credits

- [WritingTools](https://github.com/theJayTea/WritingTools) - Inspiration
- [PySide6](https://doc.qt.io/qtforpython-6/) - GUI framework
- [pynput](https://github.com/moses-palmer/pynput) - Global hotkey
- [pyperclip](https://github.com/asweigart/pyperclip) - Clipboard access

## 📄 License

This project is licensed under the **GNU General Public License v3.0** (GPL-3.0).

Copyright (c) 2026 ICSLI

See [LICENSE](LICENSE) for details.

---

**Quill** 🪶 - AI-powered writing assistant for Windows
