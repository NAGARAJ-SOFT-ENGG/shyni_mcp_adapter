"""
Gemini API Key Tester

Tests the Gemini API key configuration and allows testing with custom prompts.
Usage: python test_gemini_api.py
"""

import os
import sys
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv


def load_api_key() -> Optional[str]:
    """Load Gemini API key from .env file or environment variables.
    
    Returns:
        API key if found, None otherwise
    """
    # Explicitly point to the .env file in the same directory as this script
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path=env_path, override=True)

    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env file or environment variables.")
        print("\nTo fix this, create a file named .env in your project directory and add the line:")
        print("GEMINI_API_KEY=your_api_key_here")
        return None

    # For security, we'll only print the last 4 characters of the key
    print(f"✓ API key loaded from environment (ending in ...{api_key[-4:]})")
    
    return api_key


def test_gemini_api(api_key: str) -> bool:
    """Test if Gemini API key is valid.
    
    Args:
        api_key: Gemini API key to test
        
    Returns:
        True if API key is valid, False otherwise
    """
    try:
        genai.configure(api_key=api_key)
        print("✓ API key configured successfully")
        
        # Test the API with a simple call
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content("Say 'API Key Valid'")
        
        if response and response.text:
            print("✓ API connection successful")
            print(f"  Response: {response.text}")
            return True
        else:
            print("✗ API returned empty response")
            return False
            
    except Exception as e:
        print(f"✗ API Error: {str(e)}")
        return False


def chat_with_gemini(api_key: str) -> None:
    """Interactive chat with Gemini.
    
    Args:
        api_key: Gemini API key
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    print("\n" + "=" * 60)
    print("Gemini API - Interactive Chat")
    print("=" * 60)
    print("Enter your prompts below (type 'exit' to quit)\n")
    
    while True:
        try:
            prompt = input("You: ").strip()
            
            if prompt.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye!")
                break
            
            if not prompt:
                print("Please enter a prompt.\n")
                continue
            
            print("\nGenerating response...", end=" ", flush=True)
            response = model.generate_content(prompt)
            print("Done!")
            print(f"\nGemini: {response.text}\n")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            break
        except Exception as e:
            print(f"\nError: {str(e)}\n")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Gemini API Key Tester")
    print("=" * 60)
    
    # Load API key
    print("1. Loading API key...")
    api_key = load_api_key()
    
    if not api_key:
        sys.exit(1)
    
    # Test API key
    print("\n2. Testing API key...")
    if not test_gemini_api(api_key):
        print("\nAPI key test failed. Please check:")
        print("  - API key is correct")
        print("  - API is enabled in Google Cloud Console")
        print("  - You have sufficient quota")
        sys.exit(1)
    
    # Start interactive chat
    print("\n3. Starting interactive chat...")
    chat_with_gemini(api_key)


if __name__ == "__main__":
    main()
