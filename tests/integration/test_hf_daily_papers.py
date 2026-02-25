import sys
import os

# Ensure the project root is in python path
sys.path.append(os.getcwd())

from src.tools.hf_daily_papers import get_huggingface_papers_tool

def test_daily_papers():
    target_date = "2025-12-16"
    print(f"Testing Hugging Face Daily Papers for date: {target_date}")
    
    try:
        # invoke expecting a dict with the argument name
        result = get_huggingface_papers_tool.invoke({"target_date": target_date, "limit": 5})
        print("\n--- Result ---")
        print(result)
        print("\n--- End Result ---")
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_daily_papers()
