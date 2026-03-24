#!/usr/bin/env python3
"""
Agentic Document Processor - Run Script
Manages all services for the document processing pipeline
"""

import os
import sys
import subprocess
import time
import signal
import socket
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

processes = []
LOG_DIR = Path("logs")


def print_banner():
    """Print application banner"""
    print(f"""
{BLUE}{BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     Agentic Document Processor with LangGraph            ║
║     Multi-Agent Pipeline for Document Processing         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{RESET}
""")


def check_env_file():
    """Check if .env file exists"""
    if not Path('.env').exists():
        print(f"{YELLOW}⚠️  Warning: .env file not found{RESET}")
        print(
            f"{YELLOW}   Copy .env.example to .env and configure your API keys{RESET}")
        response = input(f"\n{BOLD}Continue anyway? (y/n): {RESET}").lower()
        if response != 'y':
            sys.exit(0)


def check_langsmith_config():
    """Check LangSmith configuration and return status"""
    try:
        from dotenv import load_dotenv
        load_dotenv()

        tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()
        api_key = os.getenv("LANGCHAIN_API_KEY", "")
        project = os.getenv("LANGCHAIN_PROJECT", "agentic-doc-processor")

        is_enabled = tracing == "true" and api_key and api_key != "your_langsmith_api_key_here"

        return {
            'enabled': is_enabled,
            'project': project,
            'tracing': tracing,
            'has_key': bool(api_key and api_key != "your_langsmith_api_key_here")
        }
    except:
        return {'enabled': False, 'project': '', 'tracing': 'false', 'has_key': False}


def check_venv():
    """Check if virtual environment is activated"""
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print(f"{YELLOW}⚠️  Virtual environment not activated{RESET}")
        print(f"{YELLOW}   Run: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate (Mac/Linux){RESET}")
        response = input(f"\n{BOLD}Continue anyway? (y/n): {RESET}").lower()
        if response != 'y':
            sys.exit(0)


def _ensure_log_dir():
    """Ensure service log directory exists."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Check if a TCP port is accepting connections."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _tail_log(path: Path, max_chars: int = 3000) -> str:
    """Return the tail of a log file for quick diagnostics."""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]
    except Exception:
        return ""


def start_service(name, command, port=None, startup_timeout=45):
    """Start a service in the background with health checks and log capture."""
    print(f"{BLUE}🚀 Starting {name}...{RESET}")
    try:
        _ensure_log_dir()
        safe_name = name.lower().replace(" ", "_")
        stdout_log = LOG_DIR / f"{safe_name}.out.log"
        stderr_log = LOG_DIR / f"{safe_name}.err.log"

        out_f = stdout_log.open("w", encoding="utf-8")
        err_f = stderr_log.open("w", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        if os.name == 'nt':  # Windows
            process = subprocess.Popen(
                command,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=out_f,
                stderr=err_f,
                env=env,
            )
        else:  # Unix/Linux/Mac
            process = subprocess.Popen(
                command,
                shell=False,
                preexec_fn=os.setsid,
                stdout=out_f,
                stderr=err_f,
                env=env,
            )

        processes.append((name, process, port, out_f, err_f, stdout_log, stderr_log))

        started = False
        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            if process.poll() is not None:
                break
            if port is None:
                started = True
                break
            if _is_port_open("127.0.0.1", port):
                started = True
                break
            time.sleep(0.5)

        if started and process.poll() is None:
            if port:
                print(f"{GREEN}✅ {name} started on port {port}{RESET}")
            else:
                print(f"{GREEN}✅ {name} started{RESET}")
            return True

        print(f"{RED}❌ Failed to start {name}{RESET}")
        if process.poll() is not None:
            print(f"{RED}   Process exited with code {process.returncode}{RESET}")
        else:
            print(f"{RED}   Startup timed out waiting for health check{RESET}")

        stderr_tail = _tail_log(stderr_log)
        stdout_tail = _tail_log(stdout_log)
        if stderr_tail:
            print(f"{YELLOW}--- {name} stderr (tail) ---{RESET}")
            print(stderr_tail)
        elif stdout_tail:
            print(f"{YELLOW}--- {name} stdout (tail) ---{RESET}")
            print(stdout_tail)
        else:
            print(f"{YELLOW}   No log output captured. Check process permissions/antivirus and Python execution policy.{RESET}")

        try:
            if process.poll() is None:
                if os.name == 'nt':
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception:
            pass

        return False
    except Exception as e:
        print(f"{RED}❌ Error starting {name}: {e}{RESET}")
        return False


def stop_all_services():
    """Stop all running services"""
    print(f"\n{YELLOW}🛑 Stopping all services...{RESET}")
    for name, process, _, out_f, err_f, _, _ in processes:
        try:
            if os.name == 'nt':  # Windows
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:  # Unix/Linux/Mac
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            print(f"{GREEN}✅ Stopped {name}{RESET}")
        except Exception as e:
            print(f"{YELLOW}⚠️  Error stopping {name}: {e}{RESET}")
        finally:
            try:
                out_f.close()
            except Exception:
                pass
            try:
                err_f.close()
            except Exception:
                pass


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    stop_all_services()
    sys.exit(0)


def main():
    """Main function"""
    print_banner()

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Pre-flight checks
    check_env_file()
    check_venv()

    # Check LangSmith configuration
    langsmith = check_langsmith_config()
    if langsmith['enabled']:
        print(f"{GREEN}✅ LangSmith tracing enabled{RESET}")
        print(f"{BLUE}   Project: {langsmith['project']}{RESET}")
        print(f"{BLUE}   📊 View traces: https://smith.langchain.com{RESET}")
    else:
        print(f"{YELLOW}ℹ️  LangSmith tracing disabled{RESET}")
        if not langsmith['has_key']:
            print(
                f"{YELLOW}   💡 Enable live graph visualization: python setup_langsmith.py{RESET}")
    print()

    print(f"\n{BOLD}Select services to start:{RESET}\n")
    print("1. API + Streamlit")
    print("2. API only")
    print("3. Streamlit only")
    print("4. LangGraph Studio (Graph Visualization)")
    print("5. Custom selection")

    choice = input(f"\n{BOLD}Enter choice (1-5): {RESET}").strip()

    services = {
        'api': False,
        'streamlit': False,
        'langgraph_studio': False
    }

    if choice == '1':
        services = {'api': True, 'streamlit': True, 'langgraph_studio': False}
    elif choice == '2':
        services['api'] = True
    elif choice == '3':
        services['streamlit'] = True
    elif choice == '4':
        services['langgraph_studio'] = True
    elif choice == '5':
        services['api'] = input("Start API? (y/n): ").lower() == 'y'
        services['streamlit'] = input(
            "Start Streamlit? (y/n): ").lower() == 'y'
        services['langgraph_studio'] = input(
            "Start LangGraph Studio? (y/n): ").lower() == 'y'
    else:
        print(f"{RED}Invalid choice{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}Starting services...{RESET}\n")

    # Start selected services
    if services['api']:
        start_service(
            "FastAPI Server",
            [sys.executable, "-m", "uvicorn", "src.api.main:api", "--host", "127.0.0.1", "--port", "8000"],
            8000,
            startup_timeout=60,
        )

    if services['streamlit']:
        start_service(
            "Streamlit UI",
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "src/ui/app.py",
                "--server.address=127.0.0.1",
                "--server.headless=true",
                "--server.port=8501",
            ],
            8501,
            startup_timeout=45,
        )

    if services['langgraph_studio']:
        # Check if langgraph CLI is available
        try:
            # Try with .venv path first (Windows)
            langgraph_cmd = ".venv\\Scripts\\langgraph.exe" if os.name == 'nt' else "langgraph"

            # Verify it exists
            subprocess.run(
                [langgraph_cmd, "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )

            # Start the server
            start_service(
                "LangGraph Studio",
                [langgraph_cmd, "dev", "--port", "8123"],
                8123
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            print(f"{RED}❌ LangGraph CLI not found{RESET}")
            print(
                f"{YELLOW}   Install with: pip install -U 'langgraph-cli[inmem]'{RESET}")
            print(f"{YELLOW}   Skipping LangGraph Studio...{RESET}\n")

    # Display access URLs
    print(f"\n{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}Services Running:{RESET}\n")

    if services['api']:
        print(f"{BLUE}📡 API Server:{RESET}       http://localhost:8000")
        print(f"{BLUE}📚 API Docs:{RESET}        http://localhost:8000/docs")

    if services['streamlit']:
        print(f"{BLUE}🎨 Streamlit UI:{RESET}    http://localhost:8501")

    if services['langgraph_studio']:
        print(f"{BLUE}📊 LangGraph Studio:{RESET} http://localhost:8123")
        print(f"{BLUE}   � Studio UI:{RESET}     https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123")
        print(f"{BLUE}   📚 API Docs:{RESET}      http://localhost:8123/docs")

    # Display LangSmith info if enabled
    langsmith = check_langsmith_config()
    if langsmith['enabled']:
        print(f"\n{BOLD}{BLUE}Live Visualization:{RESET}")
        print(f"{BLUE}📊 LangSmith:{RESET}       https://smith.langchain.com")
        print(f"{BLUE}   Project:{RESET}        {langsmith['project']}")
        print(
            f"{BLUE}   💡 Tip:{RESET}          Process a document to see real-time graph execution!")

    print(f"{BOLD}{GREEN}{'='*60}{RESET}\n")
    print(f"{YELLOW}Press Ctrl+C to stop all services{RESET}\n")

    # Keep script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_all_services()


if __name__ == "__main__":
    main()
