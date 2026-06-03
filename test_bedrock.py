"""
AWS Bedrock Llama3 8B Model Testing Script

This script provides an interactive terminal-based interface for testing
the AWS Bedrock Llama3 8B model with real-time input and output.

Features:
- Interactive multi-turn conversations
- Streaming responses for better UX
- Proper error handling and logging
- Token counting and cost estimation
- Model configuration options

Usage:
    python test_bedrock.py

Requirements:
    - AWS credentials configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - AWS region set (AWS_REGION, default: us-east-1)
    - boto3 installed
    - python-dotenv installed
"""

import json
import logging
import sys
import os
from typing import Optional, Dict, Any, Generator
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using environment variables only.")
    print("Install with: pip install python-dotenv")

# ============================================================================
# Configuration
# ============================================================================

# AWS Configuration (from .env or environment variables)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_PROFILE = os.getenv("AWS_PROFILE")

# Model Configuration
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "meta.llama3-8b-instruct-v1:0")

# Logging Configuration (console only)
LOG_LEVEL = os.getenv("BEDROCK_LOG_LEVEL", "INFO")

# Model Parameters
DEFAULT_TEMPERATURE = float(os.getenv("BEDROCK_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.getenv("BEDROCK_MAX_TOKENS", "512"))
DEFAULT_TOP_P = float(os.getenv("BEDROCK_TOP_P", "0.95"))

# Feature Flags
ENABLE_STREAMING = os.getenv("BEDROCK_ENABLE_STREAMING", "true").lower() == "true"
API_TIMEOUT = int(os.getenv("BEDROCK_API_TIMEOUT", "30"))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# ============================================================================
# Bedrock Client Wrapper
# ============================================================================

class BedrockTestClient:
    """Wrapper for AWS Bedrock Llama3 8B model interactions."""
    
    def __init__(
        self,
        region: str = AWS_REGION,
        model_id: str = MODEL_ID,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        top_p: float = DEFAULT_TOP_P
    ):
        """Initialize Bedrock client.
        
        Args:
            region: AWS region
            model_id: Bedrock model ID
            temperature: Model temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response
            top_p: Top-p sampling parameter
        """
        self.region = region
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.conversation_history = []
        
        try:
            # Create Bedrock client with proper credential handling
            session_kwargs = {"region_name": region}
            
            # Use profile if specified, otherwise use individual credentials
            if AWS_PROFILE:
                session = boto3.Session(profile_name=AWS_PROFILE)
                self.client = session.client("bedrock-runtime", region_name=region)
                logger.info(f"[OK] Using AWS profile: {AWS_PROFILE}")
            elif AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
                self.client = boto3.client(
                    "bedrock-runtime",
                    region_name=region,
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
                )
                logger.info(f"[OK] Using AWS credentials from environment")
            else:
                # Use default credential chain (IAM role, ~/.aws/credentials, etc.)
                self.client = boto3.client("bedrock-runtime", region_name=region)
                logger.info(f"[OK] Using default AWS credential chain")
            
            logger.info(f"[OK] Bedrock client initialized for region: {region}")
            logger.info(f"[OK] Model: {model_id}")
        except ClientError as e:
            logger.error(f"✗ Failed to initialize Bedrock client: {e}")
            logger.error(f"[ERROR] Failed to initialize Bedrock client: {e}")
            raise

    
    def _build_prompt(self, user_message: str, include_history: bool = True) -> str:
        """Build formatted prompt with optional conversation history.
        
        Args:
            user_message: Current user message
            include_history: Whether to include conversation history
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # Add conversation history if enabled
        if include_history and self.conversation_history:
            for turn in self.conversation_history:
                if turn["role"] == "user":
                    prompt_parts.append(f"User: {turn['content']}")
                else:
                    prompt_parts.append(f"Assistant: {turn['content']}")
            prompt_parts.append("")  # Add blank line
        
        # Add current user message
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("Assistant:")
        
        return "\n".join(prompt_parts)
    
    def _get_inference_params(self) -> Dict[str, Any]:
        """Get inference parameters for Bedrock request.
        
        Returns:
            Dictionary of inference parameters
        """
        return {
            "temperature": self.temperature,
            "max_gen_len": self.max_tokens,
            "top_p": self.top_p
        }
    
    def invoke(
        self,
        user_message: str,
        include_history: bool = True,
        streaming: Optional[bool] = None
    ) -> str:
        """Invoke model with user message.
        
        Args:
            user_message: User input message
            include_history: Whether to use conversation history
            streaming: Whether to use streaming response (None = use config default)
            
        Returns:
            Model response text
            
        Raises:
            ClientError: If API call fails
        """
        # Use streaming config if not explicitly specified
        use_streaming = streaming if streaming is not None else ENABLE_STREAMING
        
        try:
            # Build prompt
            prompt = self._build_prompt(user_message, include_history)
            logger.debug(f"Prompt: {prompt}")
            
            # Prepare request
            request_body = {
                "prompt": prompt,
                **self._get_inference_params()
            }
            
            logger.info(f"→ Sending request to {self.model_id}...")
            logger.debug(f"Request body: {json.dumps(request_body, indent=2)}")
            
            # Invoke model
            if use_streaming:
                response = self._invoke_streaming(request_body)
            else:
                response = self._invoke_standard(request_body)
            
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": response})
            
            logger.info(f"✓ Response received ({len(response)} characters)")
            logger.info(f"[OK] Response received ({len(response)} characters)")
            
            return response
            
        except ClientError as e:
            logger.error(f"✗ Bedrock API error: {e}")
            logger.error(f"[ERROR] Bedrock API error: {e}")
            raise
        except BotoCoreError as e:
            logger.error(f"✗ BotoCore error: {e}")
            logger.error(f"[ERROR] BotoCore error: {e}")
            raise
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}", exc_info=True)
            logger.error(f"[ERROR] Unexpected error: {e}", exc_info=True)
            raise
    
    def _invoke_standard(self, request_body: Dict[str, Any]) -> str:
        """Standard (non-streaming) model invocation.
        
        Args:
            request_body: Request parameters
            
        Returns:
            Model response text
        """
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )
        
        # Parse response
        response_body = json.loads(response["body"].read().decode("utf-8"))
        
        logger.debug(f"Response body: {json.dumps(response_body, indent=2)}")
        
        # Extract text from response
        if "generation" in response_body:
            return response_body["generation"].strip()
        else:
            logger.warning(f"Unexpected response format: {response_body}")
            return str(response_body)
    
    def _invoke_streaming(self, request_body: Dict[str, Any]) -> str:
        """Streaming model invocation with real-time output.
        
        Args:
            request_body: Request parameters
            
        Returns:
            Complete model response text
        """
        response = self.client.invoke_model_with_response_stream(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )
        
        # Collect streamed response
        full_response = ""
        
        try:
            for event in response["body"]:
                if "chunk" in event:
                    chunk = json.loads(event["chunk"]["bytes"].decode("utf-8"))
                    
                    if "generation" in chunk:
                        text_chunk = chunk["generation"]
                        full_response += text_chunk
                        print(text_chunk, end="", flush=True)
                        
                        # Log stop reason if present
                        if "stop_reason" in chunk:
                            logger.debug(f"Stop reason: {chunk['stop_reason']}")
            
            print()  # Newline after streaming
            return full_response.strip()
            
        except Exception as e:
            logger.error(f"✗ Error during streaming: {e}")
            logger.error(f"[ERROR] Error during streaming: {e}")
            raise
    
    def set_parameters(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None
    ) -> None:
        """Update model parameters.
        
        Args:
            temperature: Model temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response
            top_p: Top-p sampling parameter
        """
        if temperature is not None:
            if 0.0 <= temperature <= 1.0:
                self.temperature = temperature
                logger.info(f"✓ Temperature set to {temperature}")
                logger.info(f"[OK] Temperature set to {temperature}")
            else:
                logger.warning(f"Temperature must be between 0.0 and 1.0, got {temperature}")
        
        if max_tokens is not None:
            if max_tokens > 0:
                self.max_tokens = max_tokens
                logger.info(f"✓ Max tokens set to {max_tokens}")
                logger.info(f"[OK] Max tokens set to {max_tokens}")
            else:
                logger.warning(f"Max tokens must be > 0, got {max_tokens}")
        
        if top_p is not None:
            if 0.0 <= top_p <= 1.0:
                self.top_p = top_p
                logger.info(f"✓ Top-p set to {top_p}")
                logger.info(f"[OK] Top-p set to {top_p}")
            else:
                logger.warning(f"Top-p must be between 0.0 and 1.0, got {top_p}")
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("✓ Conversation history cleared")
        logger.info("[OK] Conversation history cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conversation statistics.
        
        Returns:
            Dictionary with conversation stats
        """
        user_turns = sum(1 for turn in self.conversation_history if turn["role"] == "user")
        total_chars = sum(len(turn["content"]) for turn in self.conversation_history)
        
        return {
            "turns": user_turns,
            "total_messages": len(self.conversation_history),
            "total_characters": total_chars,
            "history_length": len(self.conversation_history)
        }


# ============================================================================
# Interactive CLI
# ============================================================================

class BedrockTestCLI:
    """Interactive CLI for Bedrock model testing."""
    
    def __init__(self, client: BedrockTestClient):
        """Initialize CLI.
        
        Args:
            client: BedrockTestClient instance
        """
        self.client = client
        self.running = True
    
    def print_banner(self) -> None:
        """Print welcome banner."""
        print("\n" + "=" * 80)
        print("AWS Bedrock Llama3 8B Model Testing Interface")
        print("=" * 80)
        print(f"Model:       {self.client.model_id}")
        print(f"Region:      {self.client.region}")
        print(f"Temperature: {self.client.temperature}")
        print(f"Max Tokens:  {self.client.max_tokens}")
        print(f"Top-P:       {self.client.top_p}")
        print(f"Streaming:   {ENABLE_STREAMING}")
        print(f"Timeout:     {API_TIMEOUT}s")
        print(f"Config File: .env")
        print("=" * 80)
        print("\nCommands:")
        print("  /help       - Show this help message")
        print("  /config     - Show current configuration")
        print("  /stats      - Show conversation statistics")
        print("  /clear      - Clear conversation history")
        print("  /set        - Set model parameters (temp, tokens, top_p)")
        print("  /exit       - Exit the program")
        print("\nOr just type your message to chat with the model.")
        print("-" * 80 + "\n")
    
    def print_help(self) -> None:
        """Print help message."""
        help_text = """
Commands:
  /help                    - Show this help message
  /config                  - Show current model configuration
  /stats                   - Show conversation statistics
  /clear                   - Clear conversation history
  /set temp <value>        - Set temperature (0.0-1.0)
  /set tokens <value>      - Set max tokens (>0)
  /set top_p <value>       - Set top-p (0.0-1.0)
  /exit                    - Exit the program

Examples:
  > What is Python?
  > /set temp 0.5
  > /stats
  > /exit
        """
        print(help_text)
    
    def print_config(self) -> None:
        """Print current configuration."""
        print("\nCurrent Configuration:")
        print(f"  Model ID:        {self.client.model_id}")
        print(f"  Region:          {self.client.region}")
        print(f"  Temperature:     {self.client.temperature}")
        print(f"  Max Tokens:      {self.client.max_tokens}")
        print(f"  Top-P:           {self.client.top_p}")
        print(f"  Streaming:       {ENABLE_STREAMING}")
        print(f"  API Timeout:     {API_TIMEOUT}s")
        print(f"  Log File:        {LOG_FILE}")
        print(f"  Log Level:       {LOG_LEVEL}")
        print(f"  Config Source:   .env file")
        print()
    
    def print_stats(self) -> None:
        """Print conversation statistics."""
        stats = self.client.get_stats()
        print("\nConversation Statistics:")
        print(f"  User Turns:        {stats['turns']}")
        print(f"  Total Messages:    {stats['total_messages']}")
        print(f"  Total Characters:  {stats['total_characters']}")
        print()
    
    def handle_command(self, command: str) -> bool:
        """Handle CLI commands.
        
        Args:
            command: User command
            
        Returns:
            True to continue, False to exit
        """
        parts = command.strip().split()
        cmd = parts[0].lower() if parts else ""
        
        if cmd == "/help":
            self.print_help()
        
        elif cmd == "/config":
            self.print_config()
        
        elif cmd == "/stats":
            self.print_stats()
        
        elif cmd == "/clear":
            self.client.clear_history()
            print("✓ Conversation history cleared\n")
            print("[OK] Conversation history cleared\n")
        
        elif cmd == "/set" and len(parts) >= 3:
            param = parts[1].lower()
            try:
                value = float(parts[2])
                if param == "temp":
                    self.client.set_parameters(temperature=value)
                elif param == "tokens":
                    self.client.set_parameters(max_tokens=int(value))
                elif param == "top_p":
                    self.client.set_parameters(top_p=value)
                else:
                    print(f"✗ Unknown parameter: {param}")
                    print(f"[ERROR] Unknown parameter: {param}")
            except ValueError:
                print(f"✗ Invalid value: {parts[2]}")
                print(f"[ERROR] Invalid value: {parts[2]}")
            print()
        
        elif cmd == "/exit":
            return False
        
        elif cmd.startswith("/"):
            print(f"✗ Unknown command: {cmd}\nType /help for commands.\n")
            print(f"[ERROR] Unknown command: {cmd}\nType /help for commands.\n")
        
        else:
            return None  # Not a command, treat as message
        
        return True
    
    def run(self) -> None:
        """Run the interactive CLI."""
        self.print_banner()
        
        try:
            while self.running:
                try:
                    # Get user input
                    user_input = input("You: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Check if it's a command
                    if user_input.startswith("/"):
                        result = self.handle_command(user_input)
                        if result is False:
                            break
                        continue
                    
                    # Send message to model
                    print("\nAssistant: ", end="", flush=True)
                    response = self.client.invoke(user_input, streaming=ENABLE_STREAMING)
                    print()  # New line after response
                    
                except KeyboardInterrupt:
                    print("\n✓ Interrupted by user")
                    print("\n[OK] Interrupted by user")
                    break
                except ClientError as e:
                    logger.error(f"API Error: {e}")
                    print(f"✗ Error: {e}\n")
                    print(f"[ERROR] Error: {e}\n")
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    print(f"✗ Error: {e}\n")
                    print(f"[ERROR] Error: {e}\n")
        
        finally:
            self.print_goodbye()
    
    def print_goodbye(self) -> None:
        """Print goodbye message."""
        stats = self.client.get_stats()
        print("\n" + "=" * 80)
        print("Session Summary:")
        print(f"  Total Turns:      {stats['turns']}")
        print(f"  Total Characters: {stats['total_characters']}")
        print(f"  Log File:         {LOG_FILE}")
        print("=" * 80)
        print("Thank you for using AWS Bedrock Llama3 8B Tester!")
        print("=" * 80 + "\n")


# ============================================================================
# Main Entry Point
# ============================================================================

def main() -> None:
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("AWS Bedrock Llama3 8B Model Testing Script Started")
    logger.info("=" * 80)
    logger.info(f"Configuration loaded from environment/.env")
    logger.info(f"  Model:           {MODEL_ID}")
    logger.info(f"  Region:          {AWS_REGION}")
    logger.info(f"  Temperature:     {DEFAULT_TEMPERATURE}")
    logger.info(f"  Max Tokens:      {DEFAULT_MAX_TOKENS}")
    logger.info(f"  Top-P:           {DEFAULT_TOP_P}")
    logger.info(f"  Streaming:       {ENABLE_STREAMING}")
    logger.info(f"  API Timeout:     {API_TIMEOUT}s")
    logger.info("=" * 80)
    
    try:
        # Initialize Bedrock client
        logger.info("Initializing Bedrock client...")
        client = BedrockTestClient(
            region=AWS_REGION,
            model_id=MODEL_ID,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
            top_p=DEFAULT_TOP_P
        )
        
        # Initialize and run CLI
        logger.info("Starting interactive CLI...")
        cli = BedrockTestCLI(client)
        cli.run()
        
        logger.info("Session completed successfully")
        
    except ClientError as e:
        logger.error(f"AWS Client Error: {e}")
        print(f"\n✗ AWS Error: {e}")
        print(f"\n[ERROR] AWS Error: {e}")
        print("\nMake sure:")
        print("  1. AWS credentials are configured in .env or environment")
        print("  2. AWS region is set (default: us-east-1)")
        print("  3. You have access to Bedrock in your AWS account")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        print(f"\n[ERROR] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
