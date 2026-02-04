# Anthropic Proxy

A simple HTTP proxy server that intercepts and displays all traffic between your application and the Anthropic API (or any other HTTP service).

## Features

- Forwards all HTTP requests to a target server
- Prints all request and response details to the terminal
- Color-coded output for easy reading
- Pretty-prints JSON request/response bodies
- Preserves all headers and HTTP methods
- Configurable target host and port
- Optional display of headers (hidden by default)
- Optional display of event logging requests (hidden by default to reduce noise)
- Optional display of tools array in JSON bodies (hidden by default to reduce verbosity)
- Automatic condensing of streaming responses (merges text deltas into a single string)
- Smart JSON caching to avoid printing repeated structures (enabled by default)
- Enhanced formatting for multi-line text and content fields with syntax highlighting

## Installation

```bash
uv pip install -e .
```

## Usage

### Basic Usage (Anthropic API)

Start the proxy server:

```bash
anthropic-proxy
```

This will start a proxy server on `http://127.0.0.1:8000` that forwards traffic to `https://api.anthropic.com`.

Then, in your application, set the Anthropic base URL to point to the proxy:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8000
```

Now run your application, and all API traffic will be printed to the terminal where the proxy is running.

### Custom Configuration

```bash
# Use a different port
anthropic-proxy --port 9000

# Show headers in the output
anthropic-proxy --show-headers

# Show event logging requests (hidden by default)
anthropic-proxy --show-event-logging

# Show tools array in JSON bodies (hidden by default)
anthropic-proxy --show-tools

# Show everything
anthropic-proxy --show-headers --show-event-logging --show-tools

# Proxy to a different host
anthropic-proxy --target-host api.example.com

# Use HTTP instead of HTTPS for the target
anthropic-proxy --target-scheme http --target-host localhost:3000

# Bind to a different interface
anthropic-proxy --host 0.0.0.0 --port 8000
```

### Command-Line Options

- `--host`: Host to bind the proxy server to (default: `127.0.0.1`)
- `--port`: Port to bind the proxy server to (default: `8000`)
- `--target-host`: Target host to forward requests to (default: `api.anthropic.com`)
- `--target-scheme`: Target scheme, `http` or `https` (default: `https`)
- `--show-headers`: Display request and response headers (default: `False`)
- `--show-event-logging`: Display event logging requests (`/api/event_logging/*`) (default: `False`)
- `--show-tools`: Display tools array in request/response JSON bodies (default: `False`)
- `--no-cache-json`: Disable smart JSON caching and show full repeated structures (default: `False`)

## Example Output

When you run requests through the proxy, you'll see output like:

```
================================================================================
[1] REQUEST 2026-02-03 10:30:45.123
================================================================================
POST https://api.anthropic.com/v1/messages

Body (256 bytes):
{
  "model": "claude-opus-4-5-20251101",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": "Hello, Claude!"
    }
  ],
  "tools": "... (hidden, use --show-tools to display)"
}

--------------------------------------------------------------------------------
[1] RESPONSE 2026-02-03 10:30:45.456
--------------------------------------------------------------------------------
Status: 200

Body (512 bytes):
{
  "id": "msg_123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I help you today?"
    }
  ]
}
```

Use `--show-headers` to also display request and response headers. Use `--show-tools` to display the full tools array in request bodies (hidden by default to reduce verbosity).

### JSON Caching

By default, the proxy intelligently caches repeated JSON structures to reduce output verbosity. When the same object, array, or value appears multiple times across requests, it's shown in full the first time, then replaced with a preview on subsequent appearances:

```json
{
  "model": "claude-haiku-4-5-20251001",
  "messages": [
    {
      "role": "user",
      "content": "Hello"
    }
  ],
  "tools": [
    {
      "name": "read_file",
      "description": "Read a file from disk"
    }
  ]
}
```

The second request with the same tools array would show:

```json
{
  "model": "claude-haiku-4-5-20251001",
  "messages": [
    {
      "role": "user",
      "content": "Goodbye"
    }
  ],
  "tools": "... (cached: array with 1 items)"
}
```

This works at any level of the JSON hierarchy. Use `--no-cache-json` to disable this feature and see all repeated structures in full.

### Enhanced Text Formatting

The proxy automatically detects `text` and `content` fields in JSON and formats them with enhanced readability:

- **Multi-line strings**: Preserves newlines and indentation with blank lines before/after, making long prompts and responses easier to read
- **Syntax highlighting**: Uses a lighter cyan color for text content to distinguish it from JSON structure
- **Automatic formatting**: No configuration needed - works automatically for all text and content fields

When you have multi-line content like prompts or AI responses, they'll be displayed with preserved formatting and highlighted in a lighter color for easy reading.

### Streaming Responses

For streaming responses, the proxy automatically condenses multiple `content_block_delta` events into a single merged string:

```
--------------------------------------------------------------------------------
[8] RESPONSE 2026-02-04 13:14:42.421
--------------------------------------------------------------------------------
Status: 200

Body (1470 bytes):
Streaming response events:
  - message_start: model=claude-haiku-4-5-20251001, id=msg_01SC6SE2XC5Y83S1JgiAJr1D
    usage: input_tokens=236, output_tokens=1
  - content_block_start: index=0
  - content_block_delta (merged): "Claude Code Help Resources Overview"
  - content_block_stop
  - message_delta: stop_reason=end_turn
    usage: output_tokens=8
  - message_stop
```

## Use Cases

- Debugging API requests and responses
- Monitoring API usage
- Testing API integrations
- Learning how the Anthropic API works
- Inspecting streaming responses

## License

MIT
