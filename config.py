# AWS Configuration for Claude PDF Extractor
# Update these values with your actual AWS credentials

# AWS Credentials
AWS_ACCESS_KEY = "YOUR_ACCESS_KEY_ID"
AWS_SECRET_KEY = "YOUR_SECRET_ACCESS_KEY"
AWS_SESSION_TOKEN = "YOUR_SESSION_TOKEN"
AWS_REGION = "us-east-1"

# AWS Bedrock Model ID
# Use one of these valid model identifiers:
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"  # Claude 3 Sonnet
# MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"  # Claude 3 Haiku (faster, cheaper)
# MODEL_ID = "anthropic.claude-3-opus-20240229-v1:0"   # Claude 3 Opus (most capable)

# Optional: Customize chunk size for large documents
MAX_CHUNK_SIZE = 15000

# Optional: Delay between API calls (seconds)
API_DELAY = 1
