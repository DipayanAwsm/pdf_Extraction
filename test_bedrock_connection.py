#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import boto3


def load_config(config_path: str = "config.py"):
    """Load required AWS/Bedrock settings from config.py."""
    p = Path(config_path)
    if not p.exists():
        print(f"ERROR: Config file not found: {p}", file=sys.stderr)
        return None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("app_config", str(p))
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)  # type: ignore[attr-defined]
        required = {
            "AWS_ACCESS_KEY": getattr(cfg, "AWS_ACCESS_KEY", None),
            "AWS_SECRET_KEY": getattr(cfg, "AWS_SECRET_KEY", None),
            "AWS_SESSION_TOKEN": getattr(cfg, "AWS_SESSION_TOKEN", None),
            "AWS_REGION": getattr(cfg, "AWS_REGION", None),
            "MODEL_ID": getattr(cfg, "MODEL_ID", None),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            print(f"ERROR: Missing in config.py: {', '.join(missing)}", file=sys.stderr)
            return None
        return {
            "access_key": required["AWS_ACCESS_KEY"],
            "secret_key": required["AWS_SECRET_KEY"],
            "session_token": required["AWS_SESSION_TOKEN"],
            "region": required["AWS_REGION"],
            "model_id": required["MODEL_ID"],
        }
    except Exception as e:
        print(f"ERROR: Failed loading config: {e}", file=sys.stderr)
        return None


def main():
    cfg = load_config("config.py")
    if not cfg:
        sys.exit(1)

    try:
        session = boto3.Session(
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            aws_session_token=cfg["session_token"],
            region_name=cfg["region"],
        )
        client = session.client("bedrock-runtime")
    except Exception as e:
        print(f"ERROR: Failed to create Bedrock client: {e}", file=sys.stderr)
        sys.exit(2)

    # Minimal prompt to verify invoke_model works with Claude on Bedrock
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 64,
        "temperature": 0.0,
        "messages": [
            {"role": "user", "content": "Reply with the single word: OK"}
        ],
    }

    try:
        resp = client.invoke_model(modelId=cfg["model_id"], body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        text = payload.get("content", [{}])[0].get("text", "").strip()
        # Normalize a minimal success criterion
        if text:
            print("SUCCESS: Bedrock Claude responded:")
            print(text)
            sys.exit(0)
        else:
            print("ERROR: Empty response content from Bedrock.", file=sys.stderr)
            print(json.dumps(payload, indent=2))
            sys.exit(3)
    except Exception as e:
        print(f"ERROR: invoke_model failed: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()


