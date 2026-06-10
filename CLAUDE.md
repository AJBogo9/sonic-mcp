# sonic-mcp -- Claude Code Instructions

This is the MCP server that connects Claude Code to Sonic Pi via OSC.

## Starting Sonic Pi

Before using any tools, Sonic Pi must be running. Prefer headless mode:

```bash
sonicpi-headless   # start (waits until booted, then exits)
sonicpi-stop       # stop
sonicpi-status     # check status and current Spider port
```

If the scripts are not in PATH, they are in `scripts/` in this repo.
Install once with:
```bash
cp scripts/sonicpi-headless scripts/sonicpi-stop scripts/sonicpi-status ~/.local/bin/
chmod +x ~/.local/bin/sonicpi-{headless,stop,status}
```

The Qt GUI also works: `pw-jack sonic-pi` (required on Ubuntu 24.04 with PipeWire).
Do NOT use the desktop shortcut -- it fails to open the audio device.

## How the MCP server connects

The server auto-discovers the Spider server port from
`~/.sonic-pi/log/server-output.log` on first tool use. No manual configuration needed.

- Headless mode: fixed UDP port 4557
- Qt GUI mode: dynamic UDP port around 51235 (allocated at startup)
- OSC cues (send_cue): always fixed UDP port 4560

The Spider client is lazily initialized, so tools work correctly whether Sonic Pi
was started before or after the MCP server.

## Workflow

1. Start Sonic Pi: `sonicpi-headless`
2. Use `run_code` to send code. Always follow with `get_log` to check for errors.
3. Fix any errors before proceeding.
4. Use `stop_all` to clear all playing loops before sending a full replacement.
5. Save work with `save_song` (auto-increments version) or `save_pattern`.

## stop_all vs sonicpi-stop

- `stop_all` (MCP tool): stops all playing sounds. Sonic Pi keeps running. Use this
  between code iterations.
- `sonicpi-stop` (terminal): shuts down the entire Sonic Pi process. Use this to end
  a session.

## Port architecture

Sonic Pi 3.x runs several processes communicating over OSC:

| Port | Protocol | Process | Purpose |
|------|----------|---------|---------|
| discovered from log | UDP | Ruby Spider server | run code, stop, mixer controls |
| 4560 | UDP | Erlang router | OSC cue events (sync in Sonic Pi code) |
| 4556 | UDP | scsynth (SuperCollider) | audio synthesis |
| 4561 | UDP | Erlang scheduler | internal routing |

## Key facts

- Sonic Pi 3.2.2 on this system. `use_volume` does not exist -- use
  `set_mixer_control! amp: x` in code, or the `set_master_volume` MCP tool.
- The Qt GUI uses dynamically allocated ports starting at 51235, not the defaults
  in the source code (4557 etc.). Port discovery reads the actual port from the log.
- `pw-jack` is required on Ubuntu 24.04 because PipeWire owns the ALSA device.
  jackd is installed but will fail to open hardware; scsynth connects via PipeWire's
  JACK compatibility layer instead.
- The `send_cue` tool sends to port 4560 (Erlang), which triggers `sync "/osc*"`
  patterns in running Sonic Pi code. This is the right way to pass events to loops
  that are already running.
