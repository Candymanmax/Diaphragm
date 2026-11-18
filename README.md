<div align="center">

<h1>Diaphragm</h1>

<p><strong>Local-first text-to-speech for long-form narration on Windows and Apple Silicon macOS.</strong></p>

<p>
  <kbd>Windows</kbd>
  <kbd>macOS beta</kbd>
  <kbd>Python 3.11</kbd>
  <kbd>Windows CI: configured</kbd>
  <kbd>Beta: v0.1.0-beta.1</kbd>
  <kbd>License: All Rights Reserved</kbd>
</p>

</div>

<img src="docs/assets/diaphragm-demo.png" alt="Diaphragm demo workspace" width="100%">

Diaphragm is a text-to-speech application designed for long-form scripts. It combines model and custom voice
selection, selective regeneration, and hardware-aware automatic text splitting
for a seamless generation workflow.

## Key features

- **Multiple TTS models** - Use Original, Turbo, Multilingual V3, or Nano.
- **Custom voices** - Import and select local voice references.
- **Hardware-aware generation** - Automatically size text sections using available GPU and system memory.
- **Selective regeneration** - Edit and regenerate individual segments without recreating the entire output.
- **Integrated review** - Inspect progress, play audio, and examine individual segments inside the application.

## Getting started

Diaphragm requires 64-bit Windows or Apple Silicon macOS, with Python 3.11
matching your system's architecture. CUDA acceleration is available on compatible
Windows systems; macOS supports Apple MPS. CPU generation is available on both
platforms. An internet connection is required during initial runtime and model
downloads.

### Download the Windows build

1. Open the [latest GitHub Release](https://github.com/Candymanmax/Diaphragm/releases) and download the Windows package.
2. Extract the complete archive to a folder.
3. Run `Diaphragm.exe`.
4. On first launch, allow Diaphragm to detect your hardware and install the appropriate PyTorch runtime.
5. Install or select a TTS model, then import a voice reference.
6. Create a job, add one or more `.txt` scripts, and select **Run job**.

### Run from source

The launcher creates an isolated runtime and installs platform-appropriate
dependencies.

**Windows**

```powershell
git clone https://github.com/Candymanmax/Diaphragm.git
cd Diaphragm
.\launch.bat
```

**macOS — arm64 Python 3.11 required**

```bash
git clone https://github.com/Candymanmax/Diaphragm.git
cd Diaphragm
./launch.command
```

### Command line and subtitles

After desktop setup, run `.\diaphragm-cli.exe --help` from the extracted
Windows package. From source, run `python -m diaphragm --help` with the project runtime.

Enable **Export subtitles** under **Audio Output** or pass `--subtitles` to
`generate` to export an `.srt`.

## Supported models

| Model | Language support | Native event tags | Intended use |
|---|---|---|---|
| Original | English | No | Expressive narration with full generation controls |
| Turbo | English | Yes | Faster generation with native event tags |
| Multilingual V3 | Multilingual | No | Narration in supported non-English languages |
| Nano | English | Yes | Lightweight generation for lower-spec hardware |

Supported event tags are `[clear throat]`, `[sigh]`, `[shush]`, `[cough]`,
`[groan]`, `[sniff]`, `[gasp]`, `[chuckle]`, and `[laugh]`.

## Privacy and local storage

Diaphragm keeps generation data on your computer. By default, scripts, voice
references, jobs, model data, logs, and generated audio are stored outside the
repository:

- **Windows:** `%LOCALAPPDATA%\Diaphragm\`; Hugging Face credentials use Windows Credential Manager.
- **macOS:** `~/Library/Application Support/Diaphragm/`; Hugging Face credentials use macOS Keychain.

Internet access is needed for initial runtime and model downloads; generation
runs locally after setup.

## Beta limitations

Diaphragm is currently beta software.

- Supports 64-bit Windows and Apple Silicon macOS. Intel Macs and Rosetta runtimes are unsupported.
- Python 3.11 matching your system's architecture and an internet connection are required for first-time runtime setup.
- macOS packages currently use ad-hoc signing and are not notarized.
- TTS models are downloaded separately and may require significant disk space.
- GPU performance varies by model and hardware; CPU generation can be slow for larger models.
- Interfaces and configuration may change before version 1.0.

## Credits

- [Chatterbox](https://github.com/resemble-ai/chatterbox) - Text-to-speech models.
- [PyTorch](https://pytorch.org/) - Model inference and hardware acceleration.
- [PySide6](https://doc.qt.io/qtforpython-6/) - Desktop interface framework.
- [Catppuccin](https://catppuccin.com/) - Macchiato color palette.
- [Lucide](https://lucide.dev/) - Interface icons.

## License

Copyright © 2026 Diaphragm. All rights reserved. See [LICENSE](LICENSE) for
details.
