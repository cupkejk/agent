import os
import sys
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
    """Wraps ANSI escape sequences with \\001 and \\002 so readline calculates prompt width correctly without text overlap."""
    return f"\001{code}\002"

def print_banner():
    print(f"{Style.CYAN}╭──────────────────────────────────────────────────────────────╮{Style.RESET}")
    print(f"{Style.CYAN}│{Style.RESET}  🤖  {Style.BOLD}AGENT CHATBOT CLI{Style.RESET} (Gemini Powered)                       {Style.CYAN}│{Style.RESET}")
    print(f"{Style.CYAN}│{Style.RESET}  {Style.DIM}Commands: /help, /tools, /clear, /reset, /exit{Style.RESET}               {Style.CYAN}│{Style.RESET}")
    print(f"{Style.CYAN}╰──────────────────────────────────────────────────────────────╯{Style.RESET}\n")

def print_help():
    print(f"\n{Style.BOLD}{Style.YELLOW}💡 Available Commands:{Style.RESET}")
    print(f"  {Style.CYAN}/help{Style.RESET}    - Show this help menu")
    print(f"  {Style.CYAN}/tools{Style.RESET}   - List active tools available to the bot")
    print(f"  {Style.CYAN}/clear{Style.RESET}   - Clear terminal screen")
    print(f"  {Style.CYAN}/reset{Style.RESET}   - Reset chatbot conversation memory")
    print(f"  {Style.CYAN}/exit{Style.RESET}    - Exit the chatbot\n")

def print_tools():
    print(f"\n{Style.BOLD}{Style.MAGENTA}🛠️ Registered Tools:{Style.RESET}")
    for tool in all_tools:
        name = tool.get("name")
        desc = tool.get("description", "No description")
        print(f"  • {Style.BOLD}{name}{Style.RESET}: {desc}")
    print()

class ChatBot:
    def __init__(self, tool_map=None):
        self.interaction_id = None
        self.client = genai.Client()
        self.tool_map = tool_map or tool_map

    def reset_memory(self):
        self.interaction_id = None
        print(f"{Style.YELLOW}🔄 Conversation memory has been reset.{Style.RESET}\n")

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
                fn_args = step.arguments or {}
                
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
    print_banner()
    bot = ChatBot(tool_map=tool_map)
    
    while True:
        try:
            prompt_str = f"{rl(Style.BOLD)}{rl(Style.CYAN)}👤 You ❯ {rl(Style.RESET)}"
            user_input = input(prompt_str).strip()
            
            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit"]:
                print(f"\n{Style.GREEN}👋 Goodbye! Have a great day.{Style.RESET}\n")
                break
            elif user_input.lower() == "/clear":
                os.system("clear" if os.name == "posix" else "cls")
                print_banner()
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

            response, interaction = bot.chat(user_input)
            print(f"{Style.BOLD}{Style.GREEN}🤖 Bot ❯ {Style.RESET}{response}\n")

        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Style.GREEN}👋 Session ended. Goodbye!{Style.RESET}\n")
            sys.exit(0)