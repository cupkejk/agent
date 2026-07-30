import os
import sys
import subprocess
try:
    import termios
    import tty
    import select
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

try:
    import readline  # Enables command history (up/down arrows) and line editing in terminal
except ImportError:
    pass

from google import genai
from tools import *

# ANSI Color & Formatting System
class Style:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"

def rl(code: str) -> str:
    """Wraps ANSI escape sequences with \001 and \002 so readline calculates prompt width correctly without text overlap."""
    return f"\001{code}\002"

def print_banner(root_dir: str):
    print(f"{Style.CYAN}╭──────────────────────────────────────────────────────────────╮{Style.RESET}")
    print(f"{Style.CYAN}│{Style.RESET}  🤖  {Style.BOLD}AGENT CHATBOT CLI{Style.RESET} (Gemini Powered)                       {Style.CYAN}│{Style.RESET}")
    print(f"{Style.CYAN}│{Style.RESET}  {Style.BOLD}Root Dir:{Style.RESET} {Style.YELLOW}{root_dir}{Style.RESET}")
    print(f"{Style.CYAN}│{Style.RESET}  {Style.DIM}Instant Shell Toggle: press '!' | /cd, /help, /tools, /exit{Style.RESET}  {Style.CYAN}│{Style.RESET}")
    print(f"{Style.CYAN}╰──────────────────────────────────────────────────────────────╯{Style.RESET}\n")

def print_help():
    print(f"\n{Style.BOLD}{Style.YELLOW}💡 Available Commands & Modes:{Style.RESET}")
    print(f"  {Style.YELLOW}!{Style.RESET}          - Press '!' on empty line for instant mode toggle (no Enter key required)")
    print(f"  {Style.YELLOW}!<cmd>{Style.RESET}     - Run a single bash command instantly from Chat Mode")
    print(f"  {Style.CYAN}/cd <path>{Style.RESET}  - Change the working root directory for all tools & shell")
    print(f"  {Style.CYAN}/help{Style.RESET}      - Show this help menu")
    print(f"  {Style.CYAN}/tools{Style.RESET}     - List active tools available to the bot")
    print(f"  {Style.CYAN}/clear{Style.RESET}     - Clear terminal screen")
    print(f"  {Style.CYAN}/reset{Style.RESET}     - Reset chatbot conversation memory")
    print(f"  {Style.CYAN}/exit{Style.RESET}      - Exit the chatbot\n")

def print_tools():
    print(f"\n{Style.BOLD}{Style.MAGENTA}🛠️ Registered Tools:{Style.RESET}")
    for tool in all_tools:
        name = tool.get("name")
        desc = tool.get("description", "No description")
        print(f"  • {Style.BOLD}{name}{Style.RESET}: {desc}")
    print()

def get_input_with_instant_toggle(prompt_str: str) -> tuple[str, str]:
    """Reads input char-by-char. If '!' is pressed on an empty line, toggles mode instantly without requiring Enter.
    
    Returns:
        ("TOGGLE", "") if '!' was pressed on an empty prompt.
        ("SUBMIT", text) when Enter is pressed.
    """
    if not HAS_TERMIOS or not sys.stdin.isatty():
        text = input(prompt_str).strip()
        if text == "!":
            return ("TOGGLE", "")
        return ("SUBMIT", text)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    
    sys.stdout.write(prompt_str)
    sys.stdout.flush()
    
    buffer = []
    
    try:
        tty.setcbreak(fd)
        while True:
            char = sys.stdin.read(1)
            
            # Instant mode toggle when '!' is pressed on empty buffer
            if char == '!' and len(buffer) == 0:
                sys.stdout.write('\n')
                sys.stdout.flush()
                return ("TOGGLE", "")

            # Ctrl+C
            elif char == '\x03':
                raise KeyboardInterrupt

            # Ctrl+D
            elif char == '\x04':
                raise EOFError

            # Enter key (\n or \r)
            elif char in ('\n', '\r'):
                sys.stdout.write('\n')
                sys.stdout.flush()
                return ("SUBMIT", "".join(buffer).strip())

            # Backspace (\x7f or \x08)
            elif char in ('\x7f', '\x08'):
                if len(buffer) > 0:
                    buffer.pop()
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()

            # Escape sequence handling (e.g. arrow keys)
            elif char == '\x1b':
                if select.select([sys.stdin], [], [], 0.02)[0]:
                    sys.stdin.read(2)

            # Printable characters
            elif ord(char) >= 32:
                buffer.append(char)
                sys.stdout.write(char)
                sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class ChatBot:
    def __init__(self, tool_map=None, root_dir=None):
        self.interaction_id = None
        self.client = genai.Client()
        self.tool_map = tool_map or tool_map
        self.root_dir = os.path.abspath(root_dir) if root_dir else os.getcwd()

    def set_root_dir(self, path: str) -> bool:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(abs_path):
            print(f"{Style.RED}❌ Directory '{abs_path}' does not exist.{Style.RESET}\n")
            return False
        if not os.path.isdir(abs_path):
            print(f"{Style.RED}❌ '{abs_path}' is not a directory.{Style.RESET}\n")
            return False
        self.root_dir = abs_path
        print(f"{Style.GREEN}📁 Working root directory set to: {Style.BOLD}{self.root_dir}{Style.RESET}\n")
        return True

    def reset_memory(self):
        self.interaction_id = None
        print(f"{Style.YELLOW}🔄 Conversation memory has been reset.{Style.RESET}\n")

    def _resolve_path(self, path: str | None) -> str:
        """Resolves relative paths against self.root_dir."""
        if not path:
            return self.root_dir
        expanded = os.path.expanduser(path)
        if not os.path.isabs(expanded):
            return os.path.abspath(os.path.join(self.root_dir, expanded))
        return os.path.abspath(expanded)

    def _bind_args_to_root(self, fn_name: str, fn_args: dict) -> dict:
        """Transparently maps all tool file paths and working directories to self.root_dir without the AI knowing."""
        args = dict(fn_args)

        if fn_name == "execute_bash":
            cwd = args.get("cwd")
            args["cwd"] = self._resolve_path(cwd) if cwd else self.root_dir

        elif fn_name == "read_file":
            if "path" in args and args["path"]:
                args["path"] = self._resolve_path(args["path"])
            if "paths" in args and isinstance(args["paths"], list):
                args["paths"] = [self._resolve_path(p) for p in args["paths"]]

        elif fn_name == "list_files":
            if "directory" in args and args["directory"]:
                args["directory"] = self._resolve_path(args["directory"])
            elif "directories" in args and isinstance(args["directories"], list):
                args["directories"] = [self._resolve_path(d) for d in args["directories"]]
            else:
                args["directory"] = self.root_dir

        elif fn_name == "edit_file":
            if "path" in args and args["path"]:
                args["path"] = self._resolve_path(args["path"])

        return args

    def _ask_permission(self, fn_name, fn_args):
        """Asks user for permission before executing sensitive tools like bash commands or file modifications."""
        if fn_name == "execute_bash":
            command = fn_args.get("command", "")
            cwd = fn_args.get("cwd")
            print(f"\n{Style.CYAN}┌──────────────────────────────────────────────────────────────┐{Style.RESET}")
            print(f"{Style.CYAN}│{Style.RESET} ⚠️  {Style.BOLD}{Style.YELLOW}PERMISSION REQUEST: Bash Command Execution{Style.RESET}")
            print(f"{Style.CYAN}├──────────────────────────────────────────────────────────────┤{Style.RESET}")
            print(f"  {Style.BOLD}Command:{Style.RESET} {command}")
            if cwd:
                print(f"  {Style.BOLD}Directory:{Style.RESET} {cwd}")
            print(f"{Style.CYAN}└──────────────────────────────────────────────────────────────┘{Style.RESET}")

            try:
                prompt_str = f"{rl(Style.BOLD)}Do you grant permission to run this bash command? (Y/n): {rl(Style.RESET)}"
                choice = input(prompt_str).strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"

            if choice in ["n", "no"]:
                print(f"{Style.RED}❌ Command execution denied by user.{Style.RESET}\n")
                return False
            print(f"{Style.GREEN}✅ Permission granted.{Style.RESET}\n")

        elif fn_name == "edit_file":
            path = fn_args.get("path", "")
            target_content = fn_args.get("target_content", "")
            replacement_content = fn_args.get("replacement_content", "")
            start_line = fn_args.get("start_line")
            end_line = fn_args.get("end_line")

            range_str = f" (Lines {start_line}-{end_line})" if start_line and end_line else ""

            print(f"\n{Style.CYAN}┌──────────────────────────────────────────────────────────────┐{Style.RESET}")
            print(f"{Style.CYAN}│{Style.RESET} ⚠️  {Style.BOLD}{Style.YELLOW}PERMISSION REQUEST: File Modification{Style.RESET}{range_str}")
            print(f"{Style.CYAN}├──────────────────────────────────────────────────────────────┤{Style.RESET}")
            print(f"  {Style.BOLD}File:{Style.RESET} {path}")
            print(f"  {Style.BOLD}Proposed Diff:{Style.RESET}")
            print(f"{Style.CYAN}├──────────────────────────────────────────────────────────────┤{Style.RESET}")

            for line in target_content.splitlines():
                print(f"  {Style.RED}- {line}{Style.RESET}")

            for line in replacement_content.splitlines():
                print(f"  {Style.GREEN}+ {line}{Style.RESET}")

            print(f"{Style.CYAN}└──────────────────────────────────────────────────────────────┘{Style.RESET}")

            try:
                prompt_str = f"{rl(Style.BOLD)}Do you grant permission to modify this file? (Y/n): {rl(Style.RESET)}"
                choice = input(prompt_str).strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"

            if choice in ["n", "no"]:
                print(f"{Style.RED}❌ File modification denied by user.{Style.RESET}\n")
                return False
            print(f"{Style.GREEN}✅ Permission granted.{Style.RESET}\n")

        return True

    def _handle_tools(self, interaction):
        """Executes ALL function calls in a turn (including parallel ones) and captures model text."""
        all_text_chunks = []
        function_calls = []

        for step in interaction.steps:
            if step.type == "model_output" and step.content:
                for content_part in step.content:
                    if hasattr(content_part, "text") and content_part.text:
                        all_text_chunks.append(content_part.text)

            elif step.type == "function_call":
                function_calls.append(step)

        if function_calls:
            results_payload = []

            for step in function_calls:
                fn_name = step.name
                raw_args = step.arguments or {}
                
                # Transparently bind arguments to self.root_dir
                fn_args = self._bind_args_to_root(fn_name, raw_args)

                args_summary = ", ".join([f"{k}={repr(v)}" for k, v in fn_args.items()])
                print(f"{Style.DIM}⚙️  Executing tool: {Style.RESET}{Style.BOLD}{fn_name}{Style.RESET}({args_summary})")

                if fn_name in self.tool_map:
                    if not self._ask_permission(fn_name, fn_args):
                        result = {"error": f"Permission denied by user to execute {fn_name}."}
                    else:
                        result = self.tool_map[fn_name](**fn_args)

                    results_payload.append({
                        "type": "function_result",
                        "name": fn_name,
                        "call_id": step.id,
                        "result": str(result)
                    })

            if results_payload:
                follow_up = self.client.interactions.create(
                    model="gemini-3.5-flash-lite",
                    previous_interaction_id=self.interaction_id,
                    tools=all_tools,
                    input=results_payload
                )
                self.interaction_id = follow_up.id
                
                follow_up_text, follow_up_interaction = self._handle_tools(follow_up)
                combined_text = "\n".join(filter(None, ["\n".join(all_text_chunks), follow_up_text]))
                return combined_text, follow_up_interaction

        return "\n".join(all_text_chunks), interaction

    def chat(self, prompt):
        if self.interaction_id is None:
            interaction = self.client.interactions.create(
                model="gemini-3.5-flash-lite",
                input=prompt,
                tools=all_tools,
            )
        else:
            interaction = self.client.interactions.create(
                previous_interaction_id=self.interaction_id,
                input=prompt,
                model="gemini-3.5-flash-lite",
                tools=all_tools,
            )

        self.interaction_id = interaction.id
        captured_text, interaction = self._handle_tools(interaction)

        final_text = captured_text or interaction.output_text or ""
        return final_text, interaction


if __name__ == "__main__":
    os.system("clear" if os.name == "posix" else "cls")
    bot = ChatBot(tool_map=tool_map)
    print_banner(bot.root_dir)
    mode = "chat"
    
    while True:
        try:
            if mode == "chat":
                prompt_str = f"{Style.BOLD}{Style.CYAN}👤 You ❯ {Style.RESET}"
            else:
                prompt_str = f"{Style.BOLD}{Style.YELLOW}⚡ Shell ❯ {Style.RESET}"

            action, user_input = get_input_with_instant_toggle(prompt_str)

            # Single keypress '!' instant mode toggle
            if action == "TOGGLE":
                if mode == "chat":
                    mode = "shell"
                    print(f"{Style.YELLOW}⚡ Switched to Shell Mode. (Press '!' to return to Chat Mode){Style.RESET}\n")
                else:
                    mode = "chat"
                    print(f"{Style.CYAN}🤖 Switched to Chat Mode.{Style.RESET}\n")
                continue

            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit"]:
                print(f"\n{Style.GREEN}👋 Goodbye! Have a great day.{Style.RESET}\n")
                break
            elif user_input.lower() == "/clear":
                os.system("clear" if os.name == "posix" else "cls")
                print_banner(bot.root_dir)
                continue
            elif user_input.lower() == "/help":
                print_help()
                continue
            elif user_input.lower() == "/tools":
                print_tools()
                continue
            elif user_input.lower() == "/reset":
                bot.reset_memory()
                continue
            elif user_input.lower().startswith("/cd "):
                target_folder = user_input[4:].strip()
                bot.set_root_dir(target_folder)
                continue

            # Direct shell command execution mode
            if mode == "shell":
                print(f"{Style.DIM}Executing in {bot.root_dir}...{Style.RESET}")
                try:
                    subprocess.run(user_input, shell=True, cwd=bot.root_dir)
                except Exception as e:
                    print(f"{Style.RED}Error running command: {e}{Style.RESET}")
                print()
                continue

            # Quick single-shot bash command in chat mode (!command)
            if user_input.startswith("!"):
                cmd = user_input[1:].strip()
                if cmd:
                    print(f"{Style.DIM}Executing: {cmd} in {bot.root_dir}...{Style.RESET}")
                    try:
                        subprocess.run(cmd, shell=True, cwd=bot.root_dir)
                    except Exception as e:
                        print(f"{Style.RED}Error running command: {e}{Style.RESET}")
                    print()
                continue

            response, interaction = bot.chat(user_input)
            print(f"{Style.BOLD}{Style.GREEN}🤖 Bot ❯ {Style.RESET}{response}\n")

        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Style.GREEN}👋 Session ended. Goodbye!{Style.RESET}\n")
            sys.exit(0)