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

# Table extraction via Camelot (optional)
USE_CAMELOT = True
CAMELOT_FLAVORS = ["lattice", "stream"]  # try both
CAMELOT_PAGES = "all"

# ==============================
# Extractor Engine Selection
# ==============================
# Choose which extractor to use for page-wise processing.
# - "claude"  -> uses AWS Bedrock Claude via text_lob_llm_extractor.py
# - "openai"  -> uses OpenAI (or Azure OpenAI) via text_lob_openai_extractor.py
# If not set or invalid, the app will default to "claude" unless OpenAI creds are present,
# in which case it may auto-select "openai".
EXTRACTOR_ENGINE = "claude"  # or "openai"

# ==============================
# OpenAI / Azure OpenAI settings
# ==============================
# For OpenAI
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
OPENAI_MODEL = "gpt-4o-2024-08-06"

# For Azure OpenAI (if you use Azure endpoint)
# If using Azure OpenAI, set USE_AZURE_OPENAI=True and fill the below
USE_AZURE_OPENAI = False
AZURE_OPENAI_ENDPOINT = "https://your-azure-openai-resource.openai.azure.com/"
AZURE_OPENAI_API_KEY = "YOUR_AZURE_OPENAI_API_KEY"
AZURE_OPENAI_DEPLOYMENT_NAME = "your-deployment-name"
