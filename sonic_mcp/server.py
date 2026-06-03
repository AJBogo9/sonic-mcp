"""
Sonic Pi MCP Server

Connects Claude Code to Sonic Pi via OSC messages.
Sonic Pi must be running with a listener buffer active (see README).
"""

import os
import subprocess
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pythonosc import udp_client

SONIC_PI_HOST = "127.0.0.1"
SONIC_PI_PORT = 4560

PATTERNS_DIR = Path(os.environ.get("SONIC_PI_PATTERNS_DIR", Path.home() / "patterns"))
SONGS_DIR    = Path(os.environ.get("SONIC_PI_SONGS_DIR",    Path.home() / "songs"))

# server-errors.log captures runtime errors from eval'd code (warnings, exceptions)
# server-output.log only contains boot messages
LOG_PATH = Path.home() / ".sonic-pi" / "log" / "server-errors.log"

mcp = FastMCP("sonic-pi")
_osc = udp_client.SimpleUDPClient(SONIC_PI_HOST, SONIC_PI_PORT)

# Tracks the active pw-record process for recording
_record_proc: subprocess.Popen | None = None


def _send(address: str, *args):
    _osc.send_message(address, list(args) if args else None)


# --- Tools ---


@mcp.tool()
def run_code(code: str) -> str:
    """Send Sonic Pi code to execute. Sonic Pi must have the listener buffer running."""
    _send("/run-code", code)
    return "Code sent to Sonic Pi."


@mcp.tool()
def stop_all() -> str:
    """Stop all currently playing sounds in Sonic Pi.
    Note: this stops MCP-submitted jobs only. Jobs started from the Sonic Pi
    GUI require pressing the Stop button in the GUI itself."""
    _send("/stop-all-jobs")
    return "Stopped all jobs."


@mcp.tool()
def get_log(lines: int = 50) -> str:
    """
    Read the tail of Sonic Pi's server errors log.
    This captures runtime errors and warnings from eval'd code.
    Use this to check for errors after running code.
    """
    if not LOG_PATH.exists():
        return f"Log file not found at {LOG_PATH}. Make sure Sonic Pi has been run at least once."

    with LOG_PATH.open("r", errors="replace") as f:
        all_lines = f.readlines()

    tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
    return "".join(tail) or "(log is empty)"


@mcp.tool()
def save_pattern(name: str, category: str, code: str) -> str:
    """
    Save a reusable Sonic Pi snippet to the pattern library.
    For full songs with arrangement, use save_song instead.

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
    """
    List saved patterns in the pattern library.

    Args:
        category: Optional subfolder to filter by (e.g. "drums"). Leave empty to list all.
    """
    search_root = PATTERNS_DIR / category if category else PATTERNS_DIR

    if not search_root.exists():
        return f"No patterns found. Directory does not exist: {search_root}"

    patterns = sorted(search_root.rglob("*.rb"))
    if not patterns:
        return "No patterns found."

    lines = [str(p.relative_to(PATTERNS_DIR)) for p in patterns]
    return "\n".join(lines)


@mcp.tool()
def load_pattern(path: str) -> str:
    """
    Load a saved pattern from the library, returning its code.

    Args:
        path: Relative path from the patterns root (e.g. "drums/boom_bap_basic.rb")
    """
    target = PATTERNS_DIR / path
    if not target.exists():
        return f"Pattern not found: {target}"
    return target.read_text()


@mcp.tool()
def save_song(name: str, code: str) -> str:
    """
    Save a full song to the songs library with auto-incrementing version number.
    Creates songs/{name}/v{N}.rb, where N is one higher than the current latest version.

    Args:
        name: Song folder name in snake_case (e.g. "dark_pop_em", "aurora_borealis")
        code: The Sonic Pi Ruby code to save
    """
    song_dir = SONGS_DIR / name
    song_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(song_dir.glob("v*.rb"))
    next_v = (int(existing[-1].stem[1:]) + 1) if existing else 1

    target = song_dir / f"v{next_v}.rb"
    target.write_text(code)
    return f"Saved to {target}"


@mcp.tool()
def list_songs(name: str = "") -> str:
    """
    List songs in the songs library.

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
    """
    Load a song from the songs library.

    Args:
        name: Song folder name (e.g. "dark_pop_em")
        version: Version number to load (e.g. 3 loads v3.rb).
                 Use 0 (default) to load the latest version.
    """
    song_dir = SONGS_DIR / name
    if not song_dir.exists():
        return f"Song not found: {name}"

    if version == 0:
        versions = sorted(song_dir.glob("v*.rb"))
        if not versions:
            return f"No versions found for song: {name}"
        target = versions[-1]
    else:
        target = song_dir / f"v{version}.rb"
        if not target.exists():
            return f"Version v{version} not found for song: {name}"

    return target.read_text()


@mcp.tool()
def record_start() -> str:
    """
    Start recording Sonic Pi's audio output via PipeWire.
    Returns the output path — pass it to record_stop when done.
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
    """
    Stop the PipeWire recording and save to disk.

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
