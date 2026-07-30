import os
import subprocess

# 1. Local Python Implementation
def read_file(paths: list[str] | str | None = None, path: str | list[str] | None = None, max_lines: int = 200) -> dict | list[dict]:
    """Reads the contents of one or more text files.
    
    Args:
        paths: Path or list of paths to the file(s).
        path: Alternative parameter for a single path or list of paths (backwards compatibility).
        max_lines: Maximum lines to read per file (defaults to 200 to prevent context overflow).
    """
    target_paths = paths if paths is not None else path
    if target_paths is None:
        return {"error": "No file path provided."}

    is_single = False
    if isinstance(target_paths, str):
        target_paths = [target_paths]
        is_single = True
    elif not isinstance(target_paths, list):
        return {"error": "Invalid format for file paths."}

    results = []
    for p in target_paths:
        try:
            if not os.path.exists(p):
                results.append({"path": p, "error": f"File '{p}' does not exist."})
                continue
            
            if os.path.isdir(p):
                results.append({"path": p, "error": f"'{p}' is a directory, not a file. Use list_files instead."})
                continue

            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            content = "".join(lines[:max_lines])
            truncated = len(lines) > max_lines

            results.append({
                "path": os.path.abspath(p),
                "content": content,
                "total_lines": len(lines),
                "truncated": truncated
            })

        except Exception as e:
            results.append({"path": p, "error": f"Failed to read file: {str(e)}"})

    if is_single and len(results) == 1:
        return results[0]
    return results


# 2. Schema Declaration for Gemini API
read_file_tool = {
    "type": "function",
    "name": "read_file",
    "description": "Reads and returns the text content of one or more files from disk.",
    "parameters": {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of file paths to read (e.g., ['main.py', 'tools.py'])."
            },
            "path": {
                "type": "string",
                "description": "Single file path to read (e.g., 'main.py')."
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum number of lines to read per file. Defaults to 200."
            }
        }
    }
}

# 1. Local Python Implementation
def list_files(directories: list[str] | str | None = None, directory: str | list[str] | None = None) -> dict | list[dict]:
    """Lists all files, folders, and directories inside one or more target directory paths.
    
    Args:
        directories: Directory path or list of directory paths to list.
        directory: Target directory path or list (defaults to current directory '.' if omitted).
    """
    target_dirs = directories if directories is not None else directory
    if target_dirs is None:
        target_dirs = "."

    is_single = False
    if isinstance(target_dirs, str):
        target_dirs = [target_dirs]
        is_single = True
    elif not isinstance(target_dirs, list):
        return {"error": "Invalid format for directory paths."}

    results = []
    for d in target_dirs:
        target = d if d else "."
        try:
            entries = []
            for name in os.listdir(target):
                full_path = os.path.join(target, name)
                entries.append({
                    "name": name,
                    "is_directory": os.path.isdir(full_path)
                })
            results.append({"directory": os.path.abspath(target), "contents": entries})
        except Exception as e:
            results.append({"directory": target, "error": str(e)})

    if is_single and len(results) == 1:
        return results[0]
    return results

# 2. Tool Schema Declaration for Gemini API
list_files_tool = {
    "type": "function",
    "name": "list_files",
    "description": "Lists all files, folders, and directories inside one or more target directory paths.",
    "parameters": {
        "type": "object",
        "properties": {
            "directories": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of directory paths to list (e.g., ['.', 'funny_folder'])."
            },
            "directory": {
                "type": "string",
                "description": "Single target directory path. Pass '.' or leave empty for current working directory."
            }
        }
    }
}

get_weather_tool = {
    "type": "function",
    "name": "get_weather",
    "description": "uses a weather API to get the current weather for a given location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state or region"
            }
        },
        "required": ["location"]
    }
}

def get_weather(location):
    """Uses a weather API to get the current weather for a given location."""
    # Placeholder implementation; replace with actual API call if needed
    return f"The current weather in {location} is sunny with a temperature of 25°C."

# 1. Local Python Implementation for Bash Execution
def execute_bash(command: str, cwd: str | None = None, timeout: int = 30) -> dict:
    """Executes a bash command and returns stdout, stderr, and exit code.
    
    Args:
        command: The bash command string to run.
        cwd: Directory in which to run the command (defaults to current working directory).
        timeout: Maximum execution time in seconds (defaults to 30).
    """
    if not command or not isinstance(command, str):
        return {"error": "Command must be a non-empty string."}
    
    try:
        process = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            cwd=cwd if cwd else None,
            timeout=timeout
        )
        return {
            "command": command,
            "exit_code": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "error": f"Command timed out after {timeout} seconds."}
    except Exception as e:
        return {"command": command, "error": f"Failed to execute command: {str(e)}"}

# 2. Schema Declaration for Gemini API
execute_bash_tool = {
    "type": "function",
    "name": "execute_bash",
    "description": "Executes a bash command in the terminal and returns the stdout, stderr, and exit code.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command string to execute (e.g., 'ls -la' or 'python3 --version')."
            },
            "cwd": {
                "type": "string",
                "description": "Optional working directory path where the command should be executed."
            },
            "timeout": {
                "type": "integer",
                "description": "Optional maximum execution time in seconds. Defaults to 30."
            }
        },
        "required": ["command"]
    }
}

# 1. Local Python Implementation for File Editing
def edit_file(path: str, target_content: str, replacement_content: str, start_line: int | None = None, end_line: int | None = None) -> dict:
    """Replaces target_content with replacement_content in a file, optionally bounded by line numbers."""
    if not os.path.exists(path):
        return {"error": f"File '{path}' does not exist."}
    
    if os.path.isdir(path):
        return {"error": f"'{path}' is a directory, not a file."}

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if start_line is not None and end_line is not None:
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            
            range_content = "".join(lines[start_idx:end_idx])
            if target_content not in range_content:
                return {"error": f"target_content not found in specified line range [{start_line}:{end_line}] of '{path}'."}

            new_range_content = range_content.replace(target_content, replacement_content, 1)
            new_full_content = "".join(lines[:start_idx]) + new_range_content + "".join(lines[end_idx:])
        else:
            full_content = "".join(lines)
            if target_content not in full_content:
                return {"error": f"target_content not found in '{path}'."}
            new_full_content = full_content.replace(target_content, replacement_content, 1)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_full_content)

        return {
            "path": os.path.abspath(path),
            "message": f"Successfully updated '{path}'."
        }
    except Exception as e:
        return {"error": f"Failed to modify file: {str(e)}"}

# 2. Schema Declaration for Gemini API
edit_file_tool = {
    "type": "function",
    "name": "edit_file",
    "description": "Replaces target text with replacement text in a file, optionally targeting a specific line range.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the file to modify."
            },
            "target_content": {
                "type": "string",
                "description": "The exact text block currently in the file to be replaced."
            },
            "replacement_content": {
                "type": "string",
                "description": "The new text block that will replace target_content."
            },
            "start_line": {
                "type": "integer",
                "description": "Optional starting line number (1-indexed) of the range to target."
            },
            "end_line": {
                "type": "integer",
                "description": "Optional ending line number (1-indexed) of the range to target."
            }
        },
        "required": ["path", "target_content", "replacement_content"]
    }
}


all_tools = [get_weather_tool, list_files_tool, read_file_tool, execute_bash_tool, edit_file_tool]

tool_map = {
    "get_weather": get_weather,
    "list_files": list_files,
    "read_file": read_file,
    "execute_bash": execute_bash,
    "edit_file": edit_file
}