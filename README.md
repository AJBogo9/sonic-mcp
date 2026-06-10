# sonic-mcp

MCP server that connects Claude Code to Sonic Pi for AI-assisted beat making.

## Requirements

- Sonic Pi 3.x installed (tested on 3.2.2)
- Ubuntu 24.04 with PipeWire audio (other Linux distros may work)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

### 1. Add to Claude Code

Add this to `~/.claude/mcp.json` for global use, or a project's `.mcp.json` to keep it scoped:

```json
{
  "mcpServers": {
    "sonic-pi": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AJBogo9/sonic-mcp.git", "sonic-mcp"],
      "env": {
        "SONIC_PI_SONGS_DIR": "/home/yourname/songs",
        "SONIC_PI_PATTERNS_DIR": "/home/yourname/patterns"
      }
    }
  }
}
```

`SONIC_PI_SONGS_DIR` defaults to `~/songs` and `SONIC_PI_PATTERNS_DIR` defaults to `~/patterns`.

### 2. Start Sonic Pi

**Headless (recommended):** no GUI required.

```bash
# Install the helper scripts once
cp scripts/sonicpi-headless scripts/sonicpi-stop scripts/sonicpi-status ~/.local/bin/
chmod +x ~/.local/bin/sonicpi-headless ~/.local/bin/sonicpi-stop ~/.local/bin/sonicpi-status

# Start / stop
sonicpi-headless
sonicpi-stop
sonicpi-status
```

**Qt GUI (alternative):** use `pw-jack sonic-pi` on PipeWire systems. The desktop
shortcut fails to open the audio device on Ubuntu 24.04.

No listener buffer or manual setup is needed in either case. The MCP server connects
directly to Sonic Pi's Spider server and auto-discovers the port from the boot log.

## Tools

### Playback

| Tool | Description |
|---|---|
| `run_code(code)` | Run Sonic Pi code |
| `run_in_buffer(buffer_id, code)` | Run code in a specific buffer slot 0-9 |
| `stop_all()` | Stop all playing sounds (including GUI-run buffers) |
| `get_log(lines)` | Read the error log -- call after run_code to catch errors |

### Mixer

| Tool | Description |
|---|---|
| `set_master_volume(amp)` | Master amplitude (1.0 = unity, 0.0 = silence, max 5.0) |
| `mixer_hpf_enable(freq)` | Enable master high-pass filter at freq Hz |
| `mixer_hpf_disable()` | Disable master high-pass filter |
| `mixer_lpf_enable(freq)` | Enable master low-pass filter at freq Hz |
| `mixer_lpf_disable()` | Disable master low-pass filter |
| `mixer_stereo_mode()` | Switch master output to stereo |
| `mixer_mono_mode()` | Switch master output to mono |

### OSC cues

| Tool | Description |
|---|---|
| `send_cue(path, value)` | Send an OSC cue to trigger a `sync` in running code |

### Song and pattern library

| Tool | Description |
|---|---|
| `save_song(name, code)` | Save a full song (auto-increments version) |
| `list_songs(name)` | List all songs or versions of one song |
| `load_song(name, version)` | Load a song's code (version 0 = latest) |
| `save_pattern(name, category, code)` | Save a reusable snippet |
| `list_patterns(category)` | List patterns, optionally filtered by category |
| `load_pattern(path)` | Load a pattern's code |

### Recording

| Tool | Description |
|---|---|
| `record_start()` | Start recording via PipeWire -- returns the output path |
| `record_stop(output_path)` | Stop recording and save to disk |

## How it works

The MCP server sends OSC messages over UDP to two endpoints:

- **Spider server** (port discovered from `~/.sonic-pi/log/server-output.log`): handles
  `run_code`, `stop_all`, `run_in_buffer`, and all mixer controls. The Qt GUI uses a
  dynamically allocated port (around 51235); headless mode uses fixed port 4557.
- **Erlang OSC cues port** (fixed UDP 4560): handles `send_cue`, which triggers `sync`
  points in running Sonic Pi code.

`get_log` reads `~/.sonic-pi/log/server-errors.log`, which captures runtime errors from
evaluated code. Calling it after `run_code` lets Claude catch and fix errors automatically.

## Scripts

See [`scripts/`](scripts/) for the headless management scripts.

| Script | Description |
|---|---|
| `sonicpi-headless` | Start Sonic Pi without the Qt GUI (PipeWire/JACK audio) |
| `sonicpi-stop` | Stop a headless instance |
| `sonicpi-status` | Show running status, port, and recent log |

## Local development

```bash
git clone https://github.com/AJBogo9/sonic-mcp.git
cd sonic-mcp
pip install -e .
```

## License

MIT
