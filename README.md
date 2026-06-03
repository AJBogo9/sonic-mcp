# sonic-mcp

MCP server that connects Claude Code to Sonic Pi for AI-assisted beat making.

## Requirements

- [Sonic Pi](https://sonic-pi.net) running on your machine
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

### 1. Add to Claude Code

Add this to `~/.claude/mcp.json` for global use, or a project's `.mcp.json` to keep it scoped:

```json
{
  "mcpServers": {
    "sonic-pi": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/yourusername/sonic-mcp.git", "sonic-mcp"],
      "env": {
        "SONIC_PI_PATTERNS_DIR": "/home/yourname/patterns"
      }
    }
  }
}
```

`SONIC_PI_PATTERNS_DIR` defaults to `~/patterns` if not set.

### 2. Start the Sonic Pi listener

Paste this into a Sonic Pi buffer and hit Run **before** using any MCP tools.
It listens for incoming code over OSC and evaluates it live:

```ruby
live_loop :mcp_runner do
  use_real_time
  code = sync "/osc*/run-code"
  begin
    eval(code[0].to_s)
  rescue Exception => e
    puts "Error: #{e.message}"
  end
end
```

That's it. You can now ask Claude to write and play Sonic Pi code directly.

## Tools

| Tool | Description |
|---|---|
| `run_code` | Send Sonic Pi code to execute |
| `stop_all` | Stop all playing sounds |
| `get_log` | Read Sonic Pi's output log so Claude can see errors and self-correct |
| `save_pattern` | Save a pattern to the library |
| `list_patterns` | List patterns in the library |
| `load_pattern` | Load a pattern as a starting point for iteration |
| `record_start` | Start Sonic Pi's built-in recording |
| `record_stop` | Stop recording and save to disk |

## How it works

Claude Code calls tools over the MCP protocol. The server translates each tool call into an OSC message sent to Sonic Pi on `localhost:4560`. The `get_log` tool reads `~/.sonic-pi/log/server-output.log` so Claude can catch errors and fix them without you needing to copy-paste them.

## Local development

```bash
git clone https://github.com/yourusername/sonic-mcp.git
cd sonic-mcp
pip install -e .
```

## License

MIT
