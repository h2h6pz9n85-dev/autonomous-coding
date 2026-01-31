"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions
using Claude Code CLI.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from config import AgentConfig

from security import ALLOWED_TOOLS


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3
HEARTBEAT_INTERVAL_SECONDS = 30  # Show "still running" every 30 seconds of silence

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Text colors
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    GRAY = "\033[90m"


class StreamJsonParser:
    """
    Parser for Claude Code's stream-json output format.

    Converts NDJSON stream events into human-readable console output.

    Event types handled:
    - message_start: Session metadata
    - content_block_start: Start of text/tool_use/thinking blocks
    - content_block_delta: Incremental content (text_delta, input_json_delta, thinking_delta)
    - content_block_stop: End of content block
    - message_delta: Usage stats, stop reason
    - message_stop: End of message
    - ping: Keepalive (ignored)
    """

    def __init__(self):
        self.current_block_type: Optional[str] = None
        self.current_block_index: int = 0
        self.tool_name: Optional[str] = None
        self.tool_input_json: str = ""
        self.accumulated_text: str = ""
        self.message_id: Optional[str] = None
        self.model: Optional[str] = None

    def parse_line(self, line: str, debug: bool = False) -> Optional[str]:
        """
        Parse a single NDJSON line and return human-readable output.

        Returns None if no output should be printed for this event.
        """
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            # Not JSON - might be raw verbose output, print as-is
            return line

        if debug:
            print(f"{Colors.DIM}[DEBUG] {json.dumps(data)[:200]}{Colors.RESET}", flush=True)

        # Handle wrapped stream_event format
        if data.get("type") == "stream_event":
            event = data.get("event", {})
        else:
            event = data

        event_type = event.get("type", "")

        return self._handle_event(event_type, event)

    def _handle_event(self, event_type: str, event: dict) -> Optional[str]:
        """Route event to appropriate handler."""

        # Claude Code stream-json format (different from raw API)
        if event_type == "assistant":
            return self._handle_assistant(event)
        elif event_type == "user":
            return None  # User prompts, ignore
        elif event_type == "system":
            return self._handle_system(event)
        elif event_type == "result":
            return self._handle_result(event)

        # Raw API streaming format (for compatibility)
        elif event_type == "message_start":
            return self._handle_message_start(event)
        elif event_type == "content_block_start":
            return self._handle_content_block_start(event)
        elif event_type == "content_block_delta":
            return self._handle_content_block_delta(event)
        elif event_type == "content_block_stop":
            return self._handle_content_block_stop(event)
        elif event_type == "message_delta":
            return self._handle_message_delta(event)
        elif event_type == "message_stop":
            return self._handle_message_stop(event)
        elif event_type == "ping":
            return None  # Ignore keepalive pings
        elif event_type == "error":
            return self._handle_error(event)
        elif event_type == "progress":
            return None  # Progress events, ignore
        elif event_type == "queue-operation":
            return None  # Queue events, ignore
        elif event_type == "":
            return None  # Empty event type, ignore
        else:
            # Unknown event type - show for debugging
            return f"{Colors.DIM}[{event_type}]{Colors.RESET} "

    def _handle_message_start(self, event: dict) -> Optional[str]:
        """Handle message_start event with session metadata."""
        message = event.get("message", {})
        self.message_id = message.get("id", "unknown")
        self.model = message.get("model", "unknown")
        usage = message.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)

        return (
            f"\n{Colors.CYAN}{Colors.BOLD}━━━ Agent Response ━━━{Colors.RESET}\n"
            f"{Colors.DIM}Model: {self.model} | Input tokens: {input_tokens}{Colors.RESET}\n"
        )

    def _handle_content_block_start(self, event: dict) -> Optional[str]:
        """Handle content_block_start event."""
        self.current_block_index = event.get("index", 0)
        content_block = event.get("content_block", {})
        self.current_block_type = content_block.get("type", "")

        if self.current_block_type == "tool_use":
            self.tool_name = content_block.get("name", "unknown")
            self.tool_input_json = ""
            tool_id = content_block.get("id", "")
            return f"\n{Colors.YELLOW}⚡ Tool Call: {Colors.BOLD}{self.tool_name}{Colors.RESET}\n"
        elif self.current_block_type == "thinking":
            return f"\n{Colors.MAGENTA}💭 Thinking...{Colors.RESET}\n"
        elif self.current_block_type == "text":
            return None  # Text content will come via deltas
        else:
            return None

    def _handle_content_block_delta(self, event: dict) -> Optional[str]:
        """Handle content_block_delta event with incremental content."""
        delta = event.get("delta", {})
        delta_type = delta.get("type", "")

        if delta_type == "text_delta":
            text = delta.get("text", "")
            self.accumulated_text += text
            return text  # Stream text directly

        elif delta_type == "input_json_delta":
            partial_json = delta.get("partial_json", "")
            self.tool_input_json += partial_json
            return None  # Don't print partial JSON, wait for complete

        elif delta_type == "thinking_delta":
            thinking = delta.get("thinking", "")
            return f"{Colors.MAGENTA}{thinking}{Colors.RESET}"

        elif delta_type == "signature_delta":
            return None  # Signature for thinking verification, ignore

        else:
            return None

    def _handle_content_block_stop(self, event: dict) -> Optional[str]:
        """Handle content_block_stop event."""
        output = None

        if self.current_block_type == "tool_use" and self.tool_input_json:
            # Pretty-print the complete tool input
            try:
                parsed_input = json.loads(self.tool_input_json)
                formatted = json.dumps(parsed_input, indent=2)
                output = f"{Colors.DIM}{formatted}{Colors.RESET}\n"
            except json.JSONDecodeError:
                output = f"{Colors.DIM}{self.tool_input_json}{Colors.RESET}\n"
            self.tool_input_json = ""

        elif self.current_block_type == "thinking":
            output = f"{Colors.MAGENTA}💭 ...done thinking{Colors.RESET}\n"

        self.current_block_type = None
        self.tool_name = None
        return output

    def _handle_message_delta(self, event: dict) -> Optional[str]:
        """Handle message_delta event with stop reason and usage."""
        delta = event.get("delta", {})
        usage = event.get("usage", {})

        stop_reason = delta.get("stop_reason", "")
        output_tokens = usage.get("output_tokens", 0)

        if stop_reason:
            return f"\n{Colors.DIM}[Stop: {stop_reason} | Output tokens: {output_tokens}]{Colors.RESET}"
        return None

    def _handle_message_stop(self, event: dict) -> Optional[str]:
        """Handle message_stop event."""
        return f"\n{Colors.CYAN}{Colors.BOLD}━━━ End Response ━━━{Colors.RESET}\n"

    def _handle_error(self, event: dict) -> Optional[str]:
        """Handle error event."""
        error = event.get("error", {})
        error_type = error.get("type", "unknown")
        message = error.get("message", "Unknown error")
        return f"\n{Colors.RED}{Colors.BOLD}⚠ Error ({error_type}): {message}{Colors.RESET}\n"

    def _handle_system(self, event: dict) -> Optional[str]:
        """Handle Claude Code system events."""
        subtype = event.get("subtype", "")
        if subtype == "init":
            model = event.get("model", "unknown")
            return f"\n{Colors.CYAN}━━━ Agent Started ━━━{Colors.RESET}\n{Colors.DIM}Model: {model}{Colors.RESET}\n\n"
        return None  # Ignore other system events (hooks, etc.)

    def _handle_assistant(self, event: dict) -> Optional[str]:
        """Handle Claude Code assistant message event."""
        message = event.get("message", {})
        content_blocks = message.get("content", [])

        output_parts = []
        for block in content_blocks:
            block_type = block.get("type", "")

            if block_type == "text":
                text = block.get("text", "")
                self.accumulated_text += text
                output_parts.append(text)

            elif block_type == "tool_use":
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                output_parts.append(f"\n{Colors.YELLOW}⚡ {tool_name}{Colors.RESET}")
                if tool_input:
                    try:
                        formatted = json.dumps(tool_input, indent=2)
                        # Truncate long inputs
                        if len(formatted) > 500:
                            formatted = formatted[:500] + "..."
                        output_parts.append(f"\n{Colors.DIM}{formatted}{Colors.RESET}")
                    except (TypeError, ValueError):
                        pass
                output_parts.append("\n")

            elif block_type == "tool_result":
                # Tool results can be verbose, show summary
                output_parts.append(f"{Colors.GREEN}✓{Colors.RESET} ")

        return "".join(output_parts) if output_parts else None

    def _handle_result(self, event: dict) -> Optional[str]:
        """Handle result event (final summary)."""
        subtype = event.get("subtype", "")
        duration_ms = event.get("duration_ms", 0)
        num_turns = event.get("num_turns", 0)
        cost = event.get("total_cost_usd", 0)

        duration_str = f"{duration_ms / 1000:.1f}s" if duration_ms else ""
        cost_str = f"${cost:.4f}" if cost else ""

        status = "✓" if subtype == "success" else "✗"
        color = Colors.GREEN if subtype == "success" else Colors.RED

        return f"\n\n{color}{Colors.BOLD}━━━ {status} Session Complete ━━━{Colors.RESET}\n{Colors.DIM}Turns: {num_turns} | Duration: {duration_str} | Cost: {cost_str}{Colors.RESET}\n"

    def get_accumulated_text(self) -> str:
        """Return all accumulated text content."""
        return self.accumulated_text


def timestamp() -> str:
    """Get current timestamp for logging."""
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(message: str, level: str = "INFO") -> None:
    """Log a message with timestamp."""
    print(f"[{timestamp()}] [{level}] {message}", flush=True)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for clean file logging."""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


async def run_agent_session(
    prompt: str,
    project_dir: Path,
    model: str,
    config: "AgentConfig" = None,
    console_log_path: Optional[Path] = None,
) -> tuple[str, str]:
    """
    Run a single agent session using Claude Code CLI.

    Args:
        prompt: The prompt to send
        project_dir: Project directory path
        model: Model to use (sonnet, opus, haiku)
        config: Full agent configuration
        console_log_path: Optional path to write console output to file

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    import os

    log(f"Starting agent session with model: {model}")
    log(f"Working directory: {project_dir.resolve()}")
    if config and config.agent_state_dir and config.agent_state_dir != project_dir:
        log(f"Agent state directory: {config.agent_state_dir.resolve()}")
    log(f"Prompt length: {len(prompt)} chars")

    # Build the command
    cmd = [
        "claude",
        "-p", prompt,
        "--model", model,
        "--max-turns", "200",  # High limit for long sessions
        "--output-format", "stream-json",  # Use structured streaming output
        "--verbose",  # Required for stream-json output format
    ]

    # Add allowed tools
    for tool in ALLOWED_TOOLS:
        cmd.extend(["--allowedTools", tool])

    log(f"Allowed tools: {len(ALLOWED_TOOLS)} tools configured")
    log("Launching Claude Code CLI...")

    # Open console log file if path provided
    console_log_file = None
    if console_log_path:
        console_log_path.parent.mkdir(parents=True, exist_ok=True)
        console_log_file = open(console_log_path, 'w', encoding='utf-8')
        log(f"Console output will be saved to: {console_log_path}")

    def write_output(text: str, end: str = "", newline: bool = False) -> None:
        """Write output to both console and log file."""
        print(text, end=end, flush=True)
        if console_log_file:
            clean_text = strip_ansi(text)
            console_log_file.write(clean_text + end)
            if newline:
                console_log_file.write('\n')
            console_log_file.flush()

    try:
        # Set up environment with AGENT_STATE_DIR for scripts
        env = os.environ.copy()
        if config and config.agent_state_dir:
            env["AGENT_STATE_DIR"] = str(config.agent_state_dir.resolve())

        # Run Claude Code CLI with streaming output
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_dir.resolve()),
            env=env,
            limit=10 * 1024 * 1024,  # 10MB buffer limit
        )

        log(f"Process started with PID: {process.pid}")

        parser = StreamJsonParser()
        last_output_time = asyncio.get_event_loop().time()
        bytes_received = 0

        async def heartbeat_monitor():
            """Show heartbeat when no output for a while."""
            nonlocal last_output_time
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                elapsed = asyncio.get_event_loop().time() - last_output_time
                if elapsed >= HEARTBEAT_INTERVAL_SECONDS:
                    msg = f"[{timestamp()}] [WAIT] Agent still running... (no output for {int(elapsed)}s)"
                    write_output(msg, end="\n")

        async def read_stdout():
            """Read stdout line by line."""
            nonlocal bytes_received, last_output_time
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                bytes_received += len(line)
                last_output_time = asyncio.get_event_loop().time()
                text = line.decode('utf-8', errors='replace').rstrip('\n')
                if text:
                    output = parser.parse_line(text, debug=False)
                    if output:
                        write_output(output, end="")

        async def read_stderr():
            """Read stderr line by line."""
            nonlocal last_output_time
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                last_output_time = asyncio.get_event_loop().time()
                text = line.decode('utf-8', errors='replace').rstrip('\n')
                if text:
                    msg = f"[{timestamp()}] [STDERR] {text}"
                    write_output(msg, end="\n")

        # Start heartbeat monitor
        heartbeat_task = asyncio.create_task(heartbeat_monitor())

        try:
            # Run stdout and stderr readers concurrently
            await asyncio.gather(read_stdout(), read_stderr())
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        await process.wait()

        write_output("\n", end="")  # Newline after streaming
        log(f"Process exited with code: {process.returncode}")
        log(f"Total bytes received: {bytes_received}")
        write_output("-" * 70, end="\n")

        if process.returncode != 0:
            log(f"Process failed with exit code {process.returncode}", "ERROR")
            return "error", f"Process exited with code {process.returncode}"

        log("Session completed successfully")
        return "continue", parser.get_accumulated_text()

    except asyncio.CancelledError:
        log("Session was cancelled", "WARN")
        raise
    except Exception as e:
        log(f"Error during agent session: {e}", "ERROR")
        return "error", str(e)
    finally:
        if console_log_file:
            console_log_file.close()
