import os
import sys
import requests
from dotenv import load_dotenv

def test_openrouter_api(api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    # Using a free model to test without spending credits
    data = {
        "model": "meta-llama/llama-3-70b-instruct",
        "messages": [
            {"role": "user", "content": "Hello! Please reply with 'OpenRouter API Key is working!' if you receive this message."}
        ]
    }
    
    print("Sending request to OpenRouter...")
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() 
        result = response.json()
        print("\nSuccess! Here is the response:")
        print("-" * 50)
        print(result['choices'][0]['message']['content'])
        print("-" * 50)
        return True
    except requests.exceptions.RequestException as e:
        print(f"\nError connecting to OpenRouter API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response details: {e.response.text}")
        return False

def load_api_key():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path=env_path, override=True)
    return os.getenv("OPEN_ROUTER_API_KEY")

def chat_with_openrouter(api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    print("\n" + "=" * 60)
    print("OpenRouter API - Interactive Chat")
    print("=" * 60)
    print("Enter your prompts below (type 'exit' to quit)\n")
    
    messages = []
    
    while True:
        try:
            prompt = input("You: ").strip()
            
            if prompt.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye!")
                break
            
            if not prompt:
                print("Please enter a prompt.\n")
                continue
            
            messages.append({"role": "user", "content": prompt})
            
            data = {
                "model": "meta-llama/llama-3-70b-instruct",
                "messages": messages
            }
            
            print("\nGenerating response...", end=" ", flush=True)
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status() 
            result = response.json()
            
            reply = result['choices'][0]['message']['content']
            print("Done!")
            print(f"\nOpenRouter: {reply}\n")
            
            # Save the assistant's reply to the message history
            messages.append({"role": "assistant", "content": reply})
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            break
        except requests.exceptions.RequestException as e:
            print(f"\nError connecting to OpenRouter API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response details: {e.response.text}")
            if messages:
                messages.pop() # Remove the failed prompt from history
        except Exception as e:
            print(f"\nError: {str(e)}\n")
            if messages:
                messages.pop() # Remove the failed prompt from history

def main():
    print("=" * 60)
    print("OpenRouter API Key Tester")
    print("=" * 60)
    
    print("1. Loading API key...")
    api_key = load_api_key()
    
    if not api_key:
        print("Please set your OPEN_ROUTER_API_KEY in the .env file.")
        sys.exit(1)
        
    print(f"✓ API key loaded (ending in ...{api_key[-4:]})")
    
    print("\n2. Testing API key...")
    if not test_openrouter_api(api_key):
        print("\nAPI key test failed. Please check your key.")
        sys.exit(1)
        
    print("\n3. Starting interactive chat...")
    chat_with_openrouter(api_key)

if __name__ == "__main__":
    main()