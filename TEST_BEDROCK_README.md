# AWS Bedrock Llama3 8B Testing Script

## Overview

`test_bedrock.py` is a professional-grade interactive testing script for AWS Bedrock's Llama3 8B model. It provides a terminal-based CLI for real-time model interaction with streaming responses, conversation history, and configurable parameters.

## Features

✓ **Interactive Multi-turn Conversations** - Maintain context across multiple messages  
✓ **Streaming Responses** - Real-time model output for better user experience  
✓ **Conversation History** - Automatic context management across turns  
✓ **Configurable Parameters** - Adjust temperature, max tokens, and top-p on-the-fly  
✓ **Comprehensive Logging** - Full audit trail in `bedrock_test.log`  
✓ **Error Handling** - Graceful handling of AWS API errors  
✓ **Statistics Tracking** - Monitor conversation metrics  

## Prerequisites

### AWS Setup

1. **AWS Credentials** - Configure AWS credentials:
   ```bash
   aws configure
   ```
   
   Or set environment variables:
   ```bash
   set AWS_ACCESS_KEY_ID=your_access_key
   set AWS_SECRET_ACCESS_KEY=your_secret_key
   set AWS_REGION=us-east-1
   ```

2. **AWS Account with Bedrock Access**:
   - Ensure your AWS account has Bedrock enabled
   - Verify Llama3 8B model is available in your region
   - Check IAM permissions include `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`

3. **Python Dependencies**:
   ```bash
   pip install boto3
   ```

### Model Information

- **Model ID**: `meta.llama3-8b-instruct-v1:0`
- **Provider**: Meta (via AWS Bedrock)
- **Context Window**: 8192 tokens
- **Supported Regions**: us-east-1, us-west-2, eu-west-1, etc.

## Installation

1. **Copy the script**:
   ```bash
   cp test_bedrock.py your_project_directory/
   ```

2. **Install dependencies**:
   ```bash
   pip install boto3
   ```

3. **Verify AWS credentials**:
   ```bash
   aws sts get-caller-identity
   ```

## Usage

### Basic Usage

```bash
python test_bedrock.py
```

This starts the interactive CLI interface.

### Example Session

```
================================================================================
AWS Bedrock Llama3 8B Model Testing Interface
================================================================================
Model: meta.llama3-8b-instruct-v1:0
Region: us-east-1
Temperature: 0.7
Max Tokens: 512
Top-P: 0.95
================================================================================

You: What is machine learning?
Assistant: Machine learning is a subset of artificial intelligence that enables 
systems to learn and improve from experience without being explicitly programmed...

You: Tell me more about neural networks
Assistant: Neural networks are computational systems inspired by biological neural 
networks that constitute animal brains...

You: /stats
Conversation Statistics:
  User Turns:        2
  Total Messages:    4
  Total Characters:  1524

You: /exit
================================================================================
Session Summary:
  Total Turns:      2
  Total Characters: 1524
  Log File:         bedrock_test.log
================================================================================
```

## Commands

### Chat Commands

| Command | Description | Example |
|---------|-------------|---------|
| (regular text) | Send message to model | `What is AI?` |

### System Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show help message | `/help` |
| `/config` | Show current configuration | `/config` |
| `/stats` | Show conversation statistics | `/stats` |
| `/clear` | Clear conversation history | `/clear` |
| `/set temp <value>` | Set temperature (0.0-1.0) | `/set temp 0.5` |
| `/set tokens <value>` | Set max tokens | `/set tokens 1024` |
| `/set top_p <value>` | Set top-p sampling (0.0-1.0) | `/set top_p 0.9` |
| `/exit` | Exit program | `/exit` |

## Configuration

### Environment Variables

```bash
# AWS Configuration
set AWS_REGION=us-east-1
set AWS_ACCESS_KEY_ID=your_key
set AWS_SECRET_ACCESS_KEY=your_secret

# Or use AWS profile
set AWS_PROFILE=your_profile
```

### Model Parameters

Configure in the script:

```python
# Default model parameters
DEFAULT_TEMPERATURE = 0.7    # Lower = more deterministic (0.0-1.0)
DEFAULT_MAX_TOKENS = 512     # Maximum response length
DEFAULT_TOP_P = 0.95         # Nucleus sampling parameter (0.0-1.0)
```

### Temperature Guide

- **0.0** - Deterministic, focused responses
- **0.5** - Balanced, consistent outputs
- **0.7** - Default, good for general use
- **1.0** - Maximum randomness, creative responses

## Logging

All interactions are logged to `bedrock_test.log`:

```
2026-05-30 11:09:02 - app.bedrock - INFO - ✓ Bedrock client initialized
2026-05-30 11:09:03 - app.bedrock - INFO - → Sending request to meta.llama3-8b-instruct-v1:0
2026-05-30 11:09:05 - app.bedrock - INFO - ✓ Response received (256 characters)
```

## Error Handling

### Common Errors

#### 1. AWS Credentials Not Found

```
✗ AWS Error: Unable to locate credentials
```

**Solution**:
```bash
aws configure
# or
set AWS_ACCESS_KEY_ID=your_key
set AWS_SECRET_ACCESS_KEY=your_secret
```

#### 2. Model Not Available

```
✗ AWS Error: The Llama 3 8B model is not available
```

**Solution**:
- Check AWS region supports Llama3 8B
- Verify Bedrock is enabled in your account
- Enable model access in AWS Bedrock console

#### 3. Access Denied

```
✗ AWS Error: User is not authorized to perform bedrock:InvokeModel
```

**Solution**:
- Add IAM policy for Bedrock access
- Verify IAM user/role has `bedrock:InvokeModel*` permissions

### Debugging

Enable debug logging by modifying the script:

```python
logging.basicConfig(level=logging.DEBUG)
```

Then run:
```bash
python test_bedrock.py 2>&1 | tee debug.log
```

## Testing Scenarios

### 1. Basic Chat

```
You: Hello, how are you?
You: What can you help me with?
You: /exit
```

### 2. Temperature Testing

```
You: Write a creative story about space
You: /set temp 0.2
You: Write a story about space (again, more deterministic)
You: /set temp 1.0
You: Write a story about space (again, more creative)
```

### 3. Conversation Context

```
You: I'm learning Python
You: What should I learn next?  (model remembers Python context)
You: /clear
You: What should I learn next?  (context lost, generic answer)
```

### 4. Token Limit Testing

```
You: /set tokens 50
You: Tell me about quantum computing
You: /set tokens 500
You: Tell me about quantum computing (more detailed)
```

## Performance Metrics

### Typical Response Times

- **First Response**: 2-3 seconds (model initialization)
- **Subsequent Responses**: 1-2 seconds
- **Average Token Generation**: ~50-100 tokens/second

### Token Estimation

- Average token = 4 characters
- 512 tokens ≈ 2000 characters
- Response time scales roughly linearly with output tokens

## API Call Details

### Request Structure

```python
{
    "modelId": "meta.llama3-8b-instruct-v1:0",
    "body": json.dumps({
        "prompt": "formatted_prompt_with_history",
        "inference_parameters": {
            "temperature": 0.7,
            "max_gen_len": 512,
            "top_p": 0.95
        }
    })
}
```

### Response Structure

```python
{
    "generation": "model_output_text",
    "stop_reason": "end_token | length"
}
```

## Advanced Usage

### Programmatic Use

```python
from test_bedrock import BedrockTestClient

client = BedrockTestClient(
    temperature=0.5,
    max_tokens=256
)

response = client.invoke("What is AI?", streaming=False)
print(response)

stats = client.get_stats()
print(f"Turns: {stats['turns']}")
```

### Batch Testing

```python
from test_bedrock import BedrockTestClient

client = BedrockTestClient()

test_prompts = [
    "Explain machine learning",
    "What is deep learning?",
    "Difference between AI and ML"
]

for prompt in test_prompts:
    response = client.invoke(prompt)
    print(f"Q: {prompt}")
    print(f"A: {response}\n")
```

## Troubleshooting

### Script Hangs

- Check internet connection
- Verify AWS credentials are valid
- Check CloudWatch logs in AWS console
- Increase timeout if using slow connection

### Memory Issues

- Clear conversation history: `/clear`
- Reduce max tokens
- Use non-streaming mode for lower memory

### Slow Responses

- Reduce max tokens
- Lower temperature slightly
- Use smaller model if available
- Check AWS account quotas

## File Structure

```
test_bedrock.py          # Main testing script
bedrock_test.log         # Execution logs (auto-created)
```

## Logging Output

The script creates `bedrock_test.log` containing:
- Initialization logs
- API request/response details
- Conversation history
- Error traces
- Performance metrics

## Cost Estimation

Pricing varies by region and inference type. Typical costs:
- **Invocations**: $0.00015 per 1K input tokens
- **Output**: $0.0006 per 1K output tokens

Example: 1000 conversations, 200 avg input tokens, 100 avg output tokens
= (1000 × 200 × 0.00015) + (1000 × 100 × 0.0006) ≈ $0.09

## Supported AWS Regions

- us-east-1 (N. Virginia)
- us-west-2 (Oregon)
- eu-west-1 (Ireland)
- ap-southeast-1 (Singapore)
- ap-northeast-1 (Tokyo)

## Maintenance

### Log Rotation

Archive logs periodically:
```bash
# Backup current log
copy bedrock_test.log bedrock_test_backup_$(date /t).log

# Clear log (optional)
del bedrock_test.log
```

### Performance Monitoring

Check recent logs:
```bash
tail -50 bedrock_test.log
```

## Known Limitations

1. **Streaming Only** - Responses are streamed only during interactive CLI mode
2. **Single Region** - Configure one region at a time
3. **No Caching** - Each request goes to Bedrock API
4. **Max Context** - Llama3 8B has 8K token context limit

## Future Enhancements

- [ ] Multi-turn conversation file saving/loading
- [ ] Batch processing from files
- [ ] Model comparison testing
- [ ] Cost calculator
- [ ] Response quality metrics
- [ ] Fine-tuning examples

## Support

For issues:

1. Check `bedrock_test.log` for detailed errors
2. Verify AWS credentials and permissions
3. Ensure Bedrock access in AWS account
4. Review AWS Bedrock documentation
5. Check boto3 version compatibility

## License

MIT License - Feel free to use and modify

## Version

- **Version**: 1.0.0
- **Last Updated**: 2026-05-30
- **Python**: 3.8+
- **boto3**: 1.26.0+
