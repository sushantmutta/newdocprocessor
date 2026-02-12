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
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

processes = []

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
        print(f"{YELLOW}   Copy .env.example to .env and configure your API keys{RESET}")
        response = input(f"\n{BOLD}Continue anyway? (y/n): {RESET}").lower()
        if response != 'y':
            sys.exit(0)

def check_venv():
    """Check if virtual environment is activated"""
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print(f"{YELLOW}⚠️  Virtual environment not activated{RESET}")
        print(f"{YELLOW}   Run: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate (Mac/Linux){RESET}")
        response = input(f"\n{BOLD}Continue anyway? (y/n): {RESET}").lower()
        if response != 'y':
            sys.exit(0)

def start_service(name, command, port=None):
    """Start a service in the background"""
    print(f"{BLUE}🚀 Starting {name}...{RESET}")
    try:
        if os.name == 'nt':  # Windows
            process = subprocess.Popen(
                command,
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:  # Unix/Linux/Mac
            process = subprocess.Popen(
                command,
                shell=True,
                preexec_fn=os.setsid
            )
        
        processes.append((name, process, port))
        time.sleep(2)  # Give service time to start
        
        if process.poll() is None:
            if port:
                print(f"{GREEN}✅ {name} started on port {port}{RESET}")
            else:
                print(f"{GREEN}✅ {name} started{RESET}")
            return True
        else:
            print(f"{RED}❌ Failed to start {name}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}❌ Error starting {name}: {e}{RESET}")
        return False

def stop_all_services():
    """Stop all running services"""
    print(f"\n{YELLOW}🛑 Stopping all services...{RESET}")
    for name, process, _ in processes:
        try:
            if os.name == 'nt':  # Windows
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:  # Unix/Linux/Mac
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            print(f"{GREEN}✅ Stopped {name}{RESET}")
        except Exception as e:
            print(f"{YELLOW}⚠️  Error stopping {name}: {e}{RESET}")

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
    
    print(f"\n{BOLD}Select services to start:{RESET}\n")
    print("1. All services (API + Streamlit)")
    print("2. API only")
    print("3. Streamlit only")
    print("4. Custom selection")
    
    choice = input(f"\n{BOLD}Enter choice (1-4): {RESET}").strip()
    
    services = {
        'api': False,
        'streamlit': False
    }
    
    if choice == '1':
        services = {'api': True, 'streamlit': True}
    elif choice == '2':
        services['api'] = True
    elif choice == '3':
        services['streamlit'] = True
    elif choice == '4':
        services['api'] = input("Start API? (y/n): ").lower() == 'y'
        services['streamlit'] = input("Start Streamlit? (y/n): ").lower() == 'y'
    else:
        print(f"{RED}Invalid choice{RESET}")
        sys.exit(1)
    
    print(f"\n{BOLD}Starting services...{RESET}\n")
    
    # Start selected services
    if services['api']:
        start_service(
            "FastAPI Server",
            "python -m uvicorn api:api --host 127.0.0.1 --port 8000",
            8000
        )
    
    if services['streamlit']:
        start_service(
            "Streamlit UI",
            "streamlit run streamlit_app.py",
            8501
        )
    
    # Display access URLs
    print(f"\n{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}Services Running:{RESET}\n")
    
    if services['api']:
        print(f"{BLUE}📡 API Server:{RESET}       http://localhost:8000")
        print(f"{BLUE}📚 API Docs:{RESET}        http://localhost:8000/docs")
    
    if services['streamlit']:
        print(f"{BLUE}🎨 Streamlit UI:{RESET}    http://localhost:8501")
    
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
