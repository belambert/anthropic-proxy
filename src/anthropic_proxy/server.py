import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from typing import Any, Optional

import aiohttp
from aiohttp import web
from colorama import Fore, Style, init

# Initialize colorama for cross-platform color support
init(autoreset=True)

# Lighter cyan for text content
TEXT_COLOR = "\033[96m"  # Bright cyan


class ProxyServer:
    def __init__(self, target_host: str = "api.anthropic.com", target_scheme: str = "https", show_headers: bool = False, show_event_logging: bool = False, show_tools: bool = False, cache_json: bool = True):
        self.target_host = target_host
        self.target_scheme = target_scheme
        self.show_headers = show_headers
        self.show_event_logging = show_event_logging
        self.show_tools = show_tools
        self.cache_json = cache_json
        self.request_count = 0
        self.json_cache = {}  # Maps hash -> preview string

    def print_separator(self, char: str = "=", length: int = 80):
        print(Fore.CYAN + char * length)

    def format_json(self, obj: Any, indent: int = 0, in_text_field: bool = False) -> str:
        """Custom JSON formatter that handles multi-line strings specially."""
        indent_str = "  " * indent

        if obj is None:
            return "null"
        elif isinstance(obj, bool):
            return "true" if obj else "false"
        elif isinstance(obj, (int, float)):
            return str(obj)
        elif isinstance(obj, str):
            # Check if this is a multi-line string in a text/content field
            if in_text_field and '\n' in obj:
                # Format with newlines preserved, add blank line before and after
                lines = obj.split('\n')
                formatted_lines = []
                for line in lines:
                    # Escape the line content for display but keep it readable
                    formatted_lines.append(f'{indent_str}  {line}')
                return f'\n{TEXT_COLOR}{chr(10).join(formatted_lines)}\n{indent_str}{Style.RESET_ALL}'
            else:
                # Regular string - escape and quote it
                escaped = json.dumps(obj)
                # If it's in a text/content field and reasonably long, use the lighter color
                if in_text_field and len(obj) > 20:
                    return f'{TEXT_COLOR}{escaped}{Style.RESET_ALL}'
                return escaped
        elif isinstance(obj, list):
            if not obj:
                return "[]"
            items = []
            for item in obj:
                formatted_item = self.format_json(item, indent + 1, in_text_field)
                items.append(f"{indent_str}  {formatted_item}")
            return "[\n" + ",\n".join(items) + f"\n{indent_str}]"
        elif isinstance(obj, dict):
            if not obj:
                return "{}"
            items = []
            for key, value in obj.items():
                # Check if this is a text/content field
                is_text_field = key in ("text", "content")
                formatted_value = self.format_json(value, indent + 1, is_text_field)
                items.append(f'{indent_str}  "{key}": {formatted_value}')
            return "{\n" + ",\n".join(items) + f"\n{indent_str}" + "}"
        else:
            return json.dumps(obj)


    def compute_hash(self, value: Any) -> str:
        """Compute a hash for any JSON-serializable value."""
        serialized = json.dumps(value, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def create_preview(self, value: Any, max_length: int = 60) -> str:
        """Create a preview string for a value."""
        if isinstance(value, dict):
            if "type" in value and "text" in value:
                # Looks like a message content block
                text = value["text"]
                if len(text) > 40:
                    return f"dict with text: '{text[:40]}...'"
                return f"dict with text: '{text}'"
            elif "role" in value and "content" in value:
                # Looks like a message
                role = value["role"]
                content = str(value["content"])
                if len(content) > 40:
                    return f"message {role}: '{content[:40]}...'"
                return f"message {role}: '{content}'"
            elif "name" in value and "description" in value:
                # Looks like a tool definition
                return f"tool: {value['name']}"
            else:
                keys = list(value.keys())[:3]
                return f"dict with keys: {', '.join(keys)}{'...' if len(value) > 3 else ''}"
        elif isinstance(value, list):
            return f"array with {len(value)} items"
        elif isinstance(value, str):
            if len(value) > max_length:
                return f"'{value[:max_length]}...'"
            return f"'{value}'"
        else:
            return str(value)

    def cache_and_replace(self, value: Any, path: str = "") -> Any:
        """Recursively process JSON, caching repeated structures and replacing them with previews."""
        if not self.cache_json:
            return value

        # Don't cache primitive values at the top level
        if not isinstance(value, (dict, list)):
            return value

        # Compute hash for this value
        value_hash = self.compute_hash(value)

        # Check if we've seen this exact structure before
        if value_hash in self.json_cache:
            # Return a cached reference
            return f"... (cached: {self.json_cache[value_hash]})"

        # This is a new structure - add to cache
        preview = self.create_preview(value)
        self.json_cache[value_hash] = preview

        # Recursively process nested structures
        if isinstance(value, dict):
            result = {}
            for key, val in value.items():
                # Don't cache certain top-level fields
                if path == "" and key in ["model", "max_tokens", "stream"]:
                    result[key] = val
                else:
                    result[key] = self.cache_and_replace(val, f"{path}.{key}" if path else key)
            return result
        elif isinstance(value, list):
            # For arrays, check each item
            result = []
            for i, item in enumerate(value):
                result.append(self.cache_and_replace(item, f"{path}[{i}]"))
            return result

        return value

    def filter_tools(self, json_obj: dict) -> dict:
        """Replace the 'tools' key in a JSON object with an ellipsis if show_tools is False."""
        if not self.show_tools and isinstance(json_obj, dict) and "tools" in json_obj:
            # Create a copy to avoid modifying the original
            filtered = json_obj.copy()
            filtered["tools"] = "... (hidden, use --show-tools to display)"
            return filtered
        return json_obj

    def parse_streaming_response(self, body_text: str) -> str:
        """Parse and condense a streaming response with multiple events."""
        lines = body_text.strip().split('\n')
        events = []
        current_event = None
        text_deltas = []

        for line in lines:
            if line.startswith('event: '):
                if current_event:
                    events.append(current_event)
                current_event = {'event': line[7:].strip(), 'data': None}
            elif line.startswith('data: '):
                if current_event:
                    try:
                        current_event['data'] = json.loads(line[6:].strip())
                    except json.JSONDecodeError:
                        current_event['data'] = line[6:].strip()

        if current_event:
            events.append(current_event)

        # Extract text deltas
        for event in events:
            if (event['event'] == 'content_block_delta' and
                event['data'] and
                isinstance(event['data'], dict) and
                event['data'].get('type') == 'content_block_delta'):
                delta = event['data'].get('delta', {})
                if delta.get('type') == 'text_delta':
                    text_deltas.append(delta.get('text', ''))

        # Build condensed output
        output = []
        output.append("Streaming response events:")

        # Show message_start
        for event in events:
            if event['event'] == 'message_start' and event['data']:
                message_data = event['data'].get('message', {})
                output.append(f"  - message_start: model={message_data.get('model')}, id={message_data.get('id')}")
                usage = message_data.get('usage', {})
                if usage:
                    output.append(f"    usage: input_tokens={usage.get('input_tokens')}, output_tokens={usage.get('output_tokens')}")
                break

        # Show content_block_start
        for event in events:
            if event['event'] == 'content_block_start':
                output.append(f"  - content_block_start: index={event['data'].get('index', 0)}")
                break

        # Show merged text deltas
        if text_deltas:
            merged_text = ''.join(text_deltas)
            output.append(f"  - content_block_delta (merged): \"{merged_text}\"")

        # Show content_block_stop
        for event in events:
            if event['event'] == 'content_block_stop':
                output.append(f"  - content_block_stop")
                break

        # Show message_delta
        for event in events:
            if event['event'] == 'message_delta' and event['data']:
                delta = event['data'].get('delta', {})
                output.append(f"  - message_delta: stop_reason={delta.get('stop_reason')}")
                usage = event['data'].get('usage', {})
                if usage:
                    output.append(f"    usage: output_tokens={usage.get('output_tokens')}")
                break

        # Show message_stop
        for event in events:
            if event['event'] == 'message_stop':
                output.append(f"  - message_stop")
                break

        return '\n'.join(output)

    def print_request(self, method: str, path: str, headers: dict, body: Optional[bytes]):
        self.request_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        self.print_separator()
        print(f"{Fore.GREEN}[{self.request_count}] REQUEST {timestamp}")
        self.print_separator()
        print(f"{Fore.YELLOW}{method} {self.target_scheme}://{self.target_host}{path}")

        if self.show_headers:
            print(f"\n{Fore.MAGENTA}Headers:")
            for key, value in headers.items():
                print(f"  {key}: {value}")

        if body:
            print(f"\n{Fore.CYAN}Body ({len(body)} bytes):")
            try:
                # Try to parse and pretty-print JSON
                body_text = body.decode('utf-8')
                try:
                    json_body = json.loads(body_text)
                    # Apply caching to replace repeated structures
                    cached_body = self.cache_and_replace(json_body)
                    # Then filter tools if needed (after caching to avoid caching the filter message)
                    filtered_body = self.filter_tools(cached_body)
                    print(self.format_json(filtered_body))
                except json.JSONDecodeError:
                    # Not JSON, print as-is
                    print(body_text)
            except UnicodeDecodeError:
                print(f"  [Binary data: {len(body)} bytes]")
        print()

    def print_response(self, status: int, headers: dict, body: Optional[bytes]):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        self.print_separator("-")
        print(f"{Fore.GREEN}[{self.request_count}] RESPONSE {timestamp}")
        self.print_separator("-")

        status_color = Fore.GREEN if status < 400 else Fore.RED
        print(f"{status_color}Status: {status}")

        if self.show_headers:
            print(f"\n{Fore.MAGENTA}Headers:")
            for key, value in headers.items():
                print(f"  {key}: {value}")

        if body:
            print(f"\n{Fore.CYAN}Body ({len(body)} bytes):")
            try:
                # Try to parse and pretty-print JSON
                body_text = body.decode('utf-8')

                # Check if this is a streaming response
                if body_text.strip().startswith('event: '):
                    condensed = self.parse_streaming_response(body_text)
                    print(condensed)
                else:
                    try:
                        json_body = json.loads(body_text)
                        # Apply caching first to replace repeated structures
                        cached_body = self.cache_and_replace(json_body)
                        # Then filter tools if needed
                        filtered_body = self.filter_tools(cached_body)
                        print(self.format_json(filtered_body))
                    except json.JSONDecodeError:
                        # Not JSON, print as-is
                        print(body_text)
            except UnicodeDecodeError:
                print(f"  [Binary data: {len(body)} bytes]")
        print()

    async def handle_request(self, request: web.Request) -> web.Response:
        # Read the request body
        body = await request.read()

        # Prepare headers (remove hop-by-hop headers)
        headers = dict(request.headers)
        headers.pop('Host', None)
        headers.pop('Connection', None)
        headers.pop('Transfer-Encoding', None)

        # Set the correct Host header for the target
        headers['Host'] = self.target_host

        # Construct the target URL
        target_url = f"{self.target_scheme}://{self.target_host}{request.path_qs}"

        # Check if this is an event logging request
        is_event_logging = request.path.startswith('/api/event_logging')
        should_print = not is_event_logging or self.show_event_logging

        # Print the request
        if should_print:
            self.print_request(request.method, request.path_qs, headers, body if body else None)

        try:
            # Forward the request
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=body if body else None,
                    allow_redirects=False,
                ) as response:
                    # Read the response body
                    response_body = await response.read()

                    # Prepare response headers
                    response_headers = dict(response.headers)
                    response_headers.pop('Transfer-Encoding', None)
                    response_headers.pop('Connection', None)

                    # Print the response
                    if should_print:
                        self.print_response(response.status, response_headers, response_body if response_body else None)

                    # Return the response
                    return web.Response(
                        body=response_body,
                        status=response.status,
                        headers=response_headers,
                    )
        except Exception as e:
            error_msg = f"Error forwarding request: {e}"
            print(f"{Fore.RED}{error_msg}")
            return web.Response(text=error_msg, status=502)


async def create_app(target_host: str, target_scheme: str, show_headers: bool, show_event_logging: bool, show_tools: bool, cache_json: bool) -> web.Application:
    proxy = ProxyServer(target_host, target_scheme, show_headers, show_event_logging, show_tools, cache_json)
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", proxy.handle_request)
    return app


def main():
    parser = argparse.ArgumentParser(
        description="HTTP proxy server that prints all traffic to the terminal"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the proxy server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the proxy server to (default: 8000)",
    )
    parser.add_argument(
        "--target-host",
        default="api.anthropic.com",
        help="Target host to forward requests to (default: api.anthropic.com)",
    )
    parser.add_argument(
        "--target-scheme",
        default="https",
        choices=["http", "https"],
        help="Target scheme (default: https)",
    )
    parser.add_argument(
        "--show-headers",
        action="store_true",
        help="Display request and response headers (default: False)",
    )
    parser.add_argument(
        "--show-event-logging",
        action="store_true",
        help="Display event logging requests (/api/event_logging/*) (default: False)",
    )
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="Display tools array in request/response bodies (default: False)",
    )
    parser.add_argument(
        "--no-cache-json",
        action="store_true",
        help="Disable JSON caching (show full repeated structures) (default: False)",
    )

    args = parser.parse_args()

    cache_json = not args.no_cache_json

    print(f"{Fore.GREEN}Starting proxy server...")
    print(f"{Fore.CYAN}Listening on: {args.host}:{args.port}")
    print(f"{Fore.CYAN}Forwarding to: {args.target_scheme}://{args.target_host}")
    print(f"{Fore.CYAN}Show headers: {args.show_headers}")
    print(f"{Fore.CYAN}Show event logging: {args.show_event_logging}")
    print(f"{Fore.CYAN}Show tools: {args.show_tools}")
    print(f"{Fore.CYAN}Cache JSON: {cache_json}")
    print(f"{Fore.YELLOW}Press Ctrl+C to stop\n")

    app = asyncio.run(create_app(args.target_host, args.target_scheme, args.show_headers, args.show_event_logging, args.show_tools, cache_json))
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
