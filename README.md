# Agent Chatbot CLI

A Python-based command-line interface agent chatbot powered by the Google GenAI SDK and Gemini models. It supports dynamic tool execution (file reading/listing, bash command execution, weather lookups) with interactive user permission prompts for sensitive operations.

## Features

- **Gemini Powered:** Uses Gemini models for natural language interaction and tool calling.
- **Tool Integration:** Supports local tool execution including:
  - File reading and directory listing
  - Bash command execution
  - Weather information lookup
- **Safety Prompts:** Interactive permission checks before executing sensitive operations (such as bash commands or file modifications).
- **Interactive CLI:** Supports command history, colors, formatting, and slash commands (`/help`, `/tools`, `/clear`, `/reset`, `/exit`).

## Requirements

- Python 3.10+
- Google GenAI SDK (`google-genai`)
- A valid Gemini API key set in your environment (`GEMINI_API_KEY`)

## Installation

1. Clone or download the repository.
2. Install dependencies:
   ```bash
   pip install google-genai
   ```
3. Set your Gemini API key:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

## Usage

Run the main application:
```bash
python main.py
```

### Available Slash Commands

- `/help` - Show the help menu
- `/tools` - List active tools available to the bot
- `/clear` - Clear terminal screen
- `/reset` - Reset chatbot conversation memory
- `/exit` - Exit the chatbot

## License

This project is open-source and available under the MIT License.
