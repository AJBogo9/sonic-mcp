"""
Sonic Pi MCP Server

Connects Claude Code to Sonic Pi via OSC (UDP).

Port 4560 (fixed): Erlang OSC cues -- triggers sync "/osc*" events in running code.
Spider server:      UDP, port discovered from ~/.sonic-pi/log/server-output.log.
                    Defaults to 4557 (headless mode) if log is absent or unreadable.
"""

import os
import re
import subprocess
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pythonosc import udp_client

SONIC_PI_HOST = "127.0.0.1"
OSC_CUES_PORT = 4560   # Erlang OSC cues, always fixed
GUI_ID = "mcp"

PATTERNS_DIR = Path(os.environ.get("SONIC_PI_PATTERNS_DIR", Path.home() / "patterns"))
SONGS_DIR    = Path(os.environ.get("SONIC_PI_SONGS_DIR",    Path.home() / "songs"))

SERVER_OUTPUT_LOG = Path.home() / ".sonic-pi" / "log" / "server-output.log"
SERVER_ERRORS_LOG = Path.home() / ".sonic-pi" / "log" / "server-errors.log"

mcp = FastMCP("sonic-pi")

# UDP client for Erlang OSC cues (triggers sync in running Sonic Pi code)
_cues_client = udp_client.SimpleUDPClient(SONIC_PI_HOST, OSC_CUES_PORT)

# Tracks the active pw-record process
_record_proc: subprocess.Popen | None = None

# Spider server UDP client -- lazily created after port discovery
_spider_client: udp_client.SimpleUDPClient | None = None


def _discover_spider_port() -> int:
    """Read the Spider server port from the last boot log entry."""
    if not SERVER_OUTPUT_LOG.exists():
        return 4557
    with SERVER_OUTPUT_LOG.open(errors="replace") as f:
        for line in reversed(f.readlines()):
            m = re.match(r"Listen port:\s*(\d+)", line.strip())
            if m:
                return int(m.group(1))
    return 4557


def _spider() -> udp_client.SimpleUDPClient:
    """Return the Spider server UDP client, re-discovering the port if Sonic Pi restarted."""
    global _spider_client
    port = _discover_spider_port()
    if _spider_client is None or _spider_client._address[1] != port:
        _spider_client = udp_client.SimpleUDPClient(SONIC_PI_HOST, port)
    return _spider_client


def _spider_send(address: str, *args):
    """Send an OSC message to the Spider server with GUI_ID prepended."""
    _spider().send_message(address, [GUI_ID, *args])


def _cue(address: str, *args):
    """Send an OSC cue to the Erlang cues port (triggers sync in Sonic Pi code)."""
    _cues_client.send_message(address, list(args) if args else None)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def run_code(code: str) -> str:
    """Run Sonic Pi code. Sonic Pi must be running (GUI or headless)."""
    _spider_send("/run-code", code)
    return "Code sent to Sonic Pi."


@mcp.tool()
def run_in_buffer(buffer_id: int, code: str) -> str:
    """Save and run code in a specific Sonic Pi buffer slot (0-9).

    Mirrors the GUI buffer tabs. Useful for organizing live_loops across multiple slots.

    Args:
        buffer_id: Buffer index 0-9
        code: The Sonic Pi Ruby code to run
    """
    _spider_send("/save-and-run-buffer", buffer_id, code, "")
    return f"Code sent to buffer {buffer_id}."


@mcp.tool()
def stop_all() -> str:
    """Stop all currently playing sounds, including buffers started from the GUI."""
    _spider_send("/stop-all-jobs")
    return "Stopped all jobs."


@mcp.tool()
def ping() -> str:
    """Check whether Sonic Pi is running and which port it is on.

    Reads the boot log and checks that the Spider server port is open.
    Does not send any OSC message -- safe to call at any time.
    """
    import socket
    port = _discover_spider_port()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(0.1)
        sock.connect((SONIC_PI_HOST, port))
        reachable = True
    except OSError:
        reachable = False
    finally:
        sock.close()

    status = "reachable" if reachable else "not reachable"
    return f"Sonic Pi Spider server: UDP {SONIC_PI_HOST}:{port} -- {status}"


@mcp.tool()
def get_log(lines: int = 50) -> str:
    """Read the tail of Sonic Pi's server errors log.

    Captures runtime errors and warnings from eval'd code.
    Call this after run_code to check for errors.
    """
    if not SERVER_ERRORS_LOG.exists():
        return f"Log file not found at {SERVER_ERRORS_LOG}. Make sure Sonic Pi has been run at least once."

    with SERVER_ERRORS_LOG.open(errors="replace") as f:
        all_lines = f.readlines()

    tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
    return "".join(tail) or "(log is empty)"


# ---------------------------------------------------------------------------
# Mixer controls
# ---------------------------------------------------------------------------


@mcp.tool()
def set_master_volume(amp: float) -> str:
    """Set the master output volume.

    Args:
        amp: Amplitude multiplier. 1.0 is unity gain, 0.0 is silence, up to 5.0 (may clip).
    """
    _spider_send("/mixer-amp", amp, 0)
    return f"Master volume set to {amp}."


@mcp.tool()
def mixer_hpf_enable(freq: float) -> str:
    """Enable a high-pass filter on the master output.

    Args:
        freq: Cutoff frequency in Hz (e.g. 80.0 removes low rumble).
    """
    _spider_send("/mixer-hpf-enable", freq)
    return f"High-pass filter enabled at {freq} Hz."


@mcp.tool()
def mixer_hpf_disable() -> str:
    """Disable the master high-pass filter."""
    _spider_send("/mixer-hpf-disable")
    return "High-pass filter disabled."


@mcp.tool()
def mixer_lpf_enable(freq: float) -> str:
    """Enable a low-pass filter on the master output.

    Args:
        freq: Cutoff frequency in Hz (e.g. 8000.0 softens the high end).
    """
    _spider_send("/mixer-lpf-enable", freq)
    return f"Low-pass filter enabled at {freq} Hz."


@mcp.tool()
def mixer_lpf_disable() -> str:
    """Disable the master low-pass filter."""
    _spider_send("/mixer-lpf-disable")
    return "Low-pass filter disabled."


@mcp.tool()
def mixer_stereo_mode() -> str:
    """Switch master output to stereo mode (default)."""
    _spider_send("/mixer-stereo-mode")
    return "Mixer set to stereo mode."


@mcp.tool()
def mixer_mono_mode() -> str:
    """Switch master output to mono mode (sums left and right channels)."""
    _spider_send("/mixer-mono-mode")
    return "Mixer set to mono mode."


# ---------------------------------------------------------------------------
# OSC cues (for sync points in running Sonic Pi code)
# ---------------------------------------------------------------------------


@mcp.tool()
def send_cue(path: str, value: str = "") -> str:
    """Send an OSC cue to trigger a sync point in running Sonic Pi code.

    Use to trigger live_loops or one_shot blocks waiting on sync.
    Path must start with /. Example: /trigger/drop

    Args:
        path: OSC address, e.g. "/trigger/drop" or "/scene/chorus"
        value: Optional value passed as the cue argument. Integers and floats
               are sent as their native OSC types; anything else as a string.
    """
    if not value:
        _cue(path)
        return f"Cue sent: {path}"

    # Coerce to int or float when the string looks numeric, so Sonic Pi
    # code can use the value directly without parsing it.
    typed: int | float | str
    try:
        typed = int(value)
    except ValueError:
        try:
            typed = float(value)
        except ValueError:
            typed = value

    _cue(path, typed)
    return f"Cue sent: {path} ({typed!r})"


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------


@mcp.tool()
def save_pattern(name: str, category: str, code: str) -> str:
    """Save a reusable Sonic Pi snippet to the pattern library.

    For full songs, use save_song instead.

    Args:
        name: File name without extension (e.g. "boom_bap_basic")
        category: Subfolder (e.g. "drums", "melodic", "bass")
        code: The Sonic Pi Ruby code to save
    """
    target_dir = PATTERNS_DIR / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.rb"
    target.write_text(code)
    return f"Saved to {target}"


@mcp.tool()
def list_patterns(category: str = "") -> str:
    """List saved patterns in the pattern library.

    Args:
        category: Optional subfolder to filter by (e.g. "drums"). Leave empty to list all.
    """
    search_root = PATTERNS_DIR / category if category else PATTERNS_DIR

    if not search_root.exists():
        return f"No patterns found. Directory does not exist: {search_root}"

    patterns = sorted(search_root.rglob("*.rb"))
    if not patterns:
        return "No patterns found."

    return "\n".join(str(p.relative_to(PATTERNS_DIR)) for p in patterns)


@mcp.tool()
def load_pattern(path: str) -> str:
    """Load a saved pattern from the library, returning its code.

    Args:
        path: Relative path from the patterns root (e.g. "drums/boom_bap_basic.rb")
    """
    target = PATTERNS_DIR / path
    if not target.exists():
        return f"Pattern not found: {target}"
    return target.read_text()


# ---------------------------------------------------------------------------
# Song library
# ---------------------------------------------------------------------------


@mcp.tool()
def save_song(name: str, code: str) -> str:
    """Save a full song to the songs library with auto-incrementing version number.

    Creates songs/{name}/v{N}.rb where N is one higher than the current latest version.

    Args:
        name: Song folder name in snake_case (e.g. "dark_pop_em", "aurora_borealis")
        code: The Sonic Pi Ruby code to save
    """
    song_dir = SONGS_DIR / name
    song_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(song_dir.glob("v*.rb"), key=lambda p: int(p.stem[1:]))
    next_v = (int(existing[-1].stem[1:]) + 1) if existing else 1

    target = song_dir / f"v{next_v}.rb"
    target.write_text(code)
    return f"Saved to {target}"


@mcp.tool()
def list_songs(name: str = "") -> str:
    """List songs in the songs library.

    Args:
        name: Optional song name to list versions of (e.g. "dark_pop_em").
              Leave empty to list all songs and versions.
    """
    search_root = SONGS_DIR / name if name else SONGS_DIR

    if not search_root.exists():
        return f"No songs found. Directory does not exist: {search_root}"

    songs = sorted(search_root.rglob("*.rb"))
    if not songs:
        return "No songs found."

    return "\n".join(str(p.relative_to(SONGS_DIR)) for p in songs)


@mcp.tool()
def load_song(name: str, version: int = 0) -> str:
    """Load a song from the songs library.

    Args:
        name: Song folder name (e.g. "dark_pop_em")
        version: Version number to load (e.g. 3 loads v3.rb).
                 Use 0 (default) to load the latest version.
    """
    song_dir = SONGS_DIR / name
    if not song_dir.exists():
        return f"Song not found: {name}"

    if version == 0:
        versions = sorted(song_dir.glob("v*.rb"), key=lambda p: int(p.stem[1:]))
        if not versions:
            return f"No versions found for song: {name}"
        target = versions[-1]
    else:
        target = song_dir / f"v{version}.rb"
        if not target.exists():
            return f"Version v{version} not found for song: {name}"

    return target.read_text()


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


@mcp.tool()
def record_start() -> str:
    """Start recording Sonic Pi's audio output via PipeWire.

    Returns the output path -- pass it to record_stop when done.
    Requires pw-record and pw-link (pipewire-utils package).
    """
    global _record_proc
    if _record_proc and _record_proc.poll() is None:
        _record_proc.terminate()
        _record_proc.wait()

    output_path = str(Path.home() / f"sonic-pi-recording-{int(time.time())}.wav")

    _record_proc = subprocess.Popen(
        ["pw-record", "--target", "0", "--rate", "48000", "--channels", "2", output_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(1.5)

    subprocess.run(["pw-link", "SuperCollider:out_1", "pw-record:input_FL"], capture_output=True)
    subprocess.run(["pw-link", "SuperCollider:out_2", "pw-record:input_FR"], capture_output=True)

    return output_path


@mcp.tool()
def record_stop(output_path: str) -> str:
    """Stop the PipeWire recording and save to disk.

    Args:
        output_path: The path returned by record_start.
    """
    global _record_proc
    if _record_proc and _record_proc.poll() is None:
        _record_proc.terminate()
        _record_proc.wait()
        _record_proc = None
    return f"Recording saved to {output_path}."


def main():
    mcp.run()


if __name__ == "__main__":
    main()
