from app.llm_client import UnifiedLLMManager
from langchain_core.messages import HumanMessage
from unittest.mock import MagicMock

def test_fallback():
    print("🧪 Testing UnifiedLLMManager Fallback Logic...")
    
    # Initialize Manager
    manager = UnifiedLLMManager(provider="groq")
    
    # Mock Primary LLM to fail with 429
    manager.primary_llm = MagicMock()
    manager.primary_llm.invoke.side_effect = Exception("429 Too Many Requests")
    
    # Mock Fallback LLM to succeed
    manager.fallback_llm = MagicMock()
    manager.fallback_llm.invoke.return_value = MagicMock(content="Fallback Success")
    
    try:
        response = manager.invoke_with_fallback([HumanMessage(content="Test")])
        print(f"✅ Result: {response.content}")
        
        # Verify calls
        print(f"Primary Called: {manager.primary_llm.invoke.called}")
        print(f"Fallback Called: {manager.fallback_llm.invoke.called}")
        
        if manager.primary_llm.invoke.called and manager.fallback_llm.invoke.called:
            print("🚀 Fallback mechanism IS working correctly.")
        else:
            print("❌ Fallback mechanism failed.")
            
    except Exception as e:
        print(f"❌ Exception caught: {e}")

if __name__ == "__main__":
    test_fallback()
