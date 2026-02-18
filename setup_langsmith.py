"""
LangSmith Quick Setup Script
Enables LangSmith tracing for live graph visualization
"""

import os
from pathlib import Path
import sys


def check_langsmith_config():
    """Check if LangSmith is configured."""
    print("\n" + "="*70)
    print("🔍 LangSmith Configuration Check")
    print("="*70 + "\n")

    # Check environment variables
    tracing = os.getenv("LANGCHAIN_TRACING_V2", "false")
    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    project = os.getenv("LANGCHAIN_PROJECT", "agentic-doc-processor")
    endpoint = os.getenv("LANGCHAIN_ENDPOINT",
                         "https://api.smith.langchain.com")

    print(f"📍 LANGCHAIN_TRACING_V2: {tracing}")
    print(
        f"🔑 LANGCHAIN_API_KEY: {'✅ Set' if api_key and api_key != 'your_langsmith_api_key_here' else '❌ Not set'}")
    print(f"📦 LANGCHAIN_PROJECT: {project}")
    print(f"🌐 LANGCHAIN_ENDPOINT: {endpoint}")

    # Load from .env if present
    env_file = Path(".env")
    if env_file.exists():
        print(f"\n✅ .env file found: {env_file.absolute()}")

        from dotenv import load_dotenv
        load_dotenv()

        # Reload after dotenv
        tracing = os.getenv("LANGCHAIN_TRACING_V2", "false")
        api_key = os.getenv("LANGCHAIN_API_KEY", "")

    else:
        print("\n⚠️  No .env file found")
        print("   Create one from .env.example:")
        print("   cp .env.example .env")

    print("\n" + "-"*70)

    # Status
    if tracing.lower() == "true" and api_key and api_key != "your_langsmith_api_key_here":
        print("\n✅ LangSmith is ENABLED and configured!")
        print("\n📊 To view traces:")
        print("   1. Visit: https://smith.langchain.com")
        print("   2. Go to Projects → " + project)
        print("   3. Process a document (streamlit_app.py or run_cli.py)")
        print("   4. Watch the live graph visualization! 🎉")
        return True

    elif tracing.lower() == "true":
        print("\n⚠️  LangSmith tracing is ENABLED but API key is missing!")
        print("\n🔧 To fix:")
        print("   1. Sign up at: https://smith.langchain.com (FREE)")
        print("   2. Get your API key from Settings → API Keys")
        print("   3. Add to .env: LANGCHAIN_API_KEY=lsv2_pt_your_key_here")
        return False

    else:
        print("\n❌ LangSmith tracing is DISABLED")
        print("\n🎯 To enable live graph visualization:")
        print("   1. Get FREE API key: https://smith.langchain.com")
        print("   2. Update .env file:")
        print("      LANGCHAIN_TRACING_V2=true")
        print("      LANGCHAIN_API_KEY=lsv2_pt_your_key_here")
        print("   3. Restart your application")
        print("\n📖 See LANGSMITH_SETUP.md for detailed instructions")
        return False


def enable_langsmith_interactive():
    """Interactive setup wizard."""
    print("\n" + "="*70)
    print("🚀 LangSmith Setup Wizard")
    print("="*70 + "\n")

    env_file = Path(".env")

    # Check if .env exists
    if not env_file.exists():
        print("Creating .env file from template...")
        example_file = Path(".env.example")
        if example_file.exists():
            import shutil
            shutil.copy(example_file, env_file)
            print(f"✅ Created: {env_file.absolute()}")
        else:
            print("❌ .env.example not found!")
            return

    print("\n📝 To enable LangSmith:")
    print("1. Get your FREE API key from: https://smith.langchain.com")
    print("2. Go to Settings → API Keys → Create API Key")
    print("3. Copy your API key (starts with 'lsv2_pt_')")

    api_key = input(
        "\n🔑 Paste your LangSmith API key (or press Enter to skip): ").strip()

    if api_key:
        # Update .env file
        print("\nUpdating .env file...")

        with open(env_file, 'r') as f:
            content = f.read()

        # Update API key
        if "LANGCHAIN_API_KEY=" in content:
            import re
            content = re.sub(
                r'LANGCHAIN_API_KEY=.*',
                f'LANGCHAIN_API_KEY={api_key}',
                content
            )
        else:
            content += f"\nLANGCHAIN_API_KEY={api_key}\n"

        # Enable tracing
        if "LANGCHAIN_TRACING_V2=" in content:
            import re
            content = re.sub(
                r'LANGCHAIN_TRACING_V2=.*',
                'LANGCHAIN_TRACING_V2=true',
                content
            )
        else:
            content += "\nLANGCHAIN_TRACING_V2=true\n"

        # Write back
        with open(env_file, 'w') as f:
            f.write(content)

        print("✅ LangSmith configuration updated!")
        print("\n🎉 You're all set!")
        print("\nNext steps:")
        print("1. Restart your application if it's running")
        print("2. Process a document:")
        print("   streamlit run streamlit_app.py")
        print("   - OR -")
        print("   python run_cli.py dummy_prescription.txt")
        print("\n3. Open LangSmith Studio: https://smith.langchain.com")
        print("4. Go to Projects → agentic-doc-processor")
        print("5. Watch your workflow execute in real-time! 📊")

    else:
        print("\n⏭️  Skipped. You can manually edit .env file:")
        print(f"   {env_file.absolute()}")
        print("\nSet these values:")
        print("   LANGCHAIN_TRACING_V2=true")
        print("   LANGCHAIN_API_KEY=your_api_key_here")


def main():
    """Main function."""
    print("\n" + "="*70)
    print("  🔍 LangSmith Live Visualization Setup")
    print("="*70)

    print("\nLangSmith provides:")
    print("  ✅ Real-time graph visualization")
    print("  ✅ Live agent execution tracing")
    print("  ✅ Step-by-step debugging")
    print("  ✅ Performance metrics")
    print("  ✅ LLM call monitoring")

    print("\n" + "="*70)

    # Check current status
    is_configured = check_langsmith_config()

    if is_configured:
        print("\n" + "="*70)
        print("✅ LangSmith is ready to use!")
        print("="*70 + "\n")
        return

    # Offer to set up
    print("\n" + "-"*70)
    setup = input(
        "\n🔧 Would you like to set up LangSmith now? (y/n): ").strip().lower()

    if setup == 'y':
        enable_langsmith_interactive()
    else:
        print("\n📖 For manual setup, see: LANGSMITH_SETUP.md")
        print("   Quick start:")
        print("   1. Get API key: https://smith.langchain.com")
        print("   2. Update .env with your key")
        print("   3. Set LANGCHAIN_TRACING_V2=true")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("\n⚠️  python-dotenv not installed")
        print("   Install with: pip install python-dotenv")
        sys.exit(1)

    main()
