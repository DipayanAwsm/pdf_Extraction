import argparse
import json
import os
import time
import uuid
from typing import Dict, List, Tuple

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is not installed. Install it with: pip install boto3")
    raise

import pandas as pd


def load_aws_config(config_path: str) -> Dict[str, str]:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r") as f:
        data = json.load(f)
    return {
        "aws_access_key_id": data.get("access_key"),
        "aws_secret_access_key": data.get("secret_key"),
        "aws_session_token": data.get("session_token"),
        "region_name": data.get("region", "us-east-1"),
    }


def get_boto_clients(config_path: str) -> Tuple[object, object]:
    cfg = load_aws_config(config_path)
    s3 = boto3.client("s3", **cfg) if cfg else boto3.client("s3")
    textract = boto3.client("textract", **cfg) if cfg else boto3.client("textract")
    return s3, textract


def upload_to_s3(s3_client, file_path: str, bucket: str, key_prefix: str = "textract-input/") -> str:
    base_name = os.path.basename(file_path)
    unique_key = f"{key_prefix}{uuid.uuid4()}-{base_name}"
    s3_client.upload_file(file_path, bucket, unique_key)
    return unique_key


def start_textract_job(textract_client, bucket: str, key: str) -> str:
    response = textract_client.start_document_analysis(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
        FeatureTypes=["TABLES"],
    )
    return response["JobId"]


def wait_for_job(textract_client, job_id: str, poll_seconds: int = 5) -> None:
    while True:
        res = textract_client.get_document_analysis(JobId=job_id, MaxResults=1)
        status = res.get("JobStatus")
        if status in ("SUCCEEDED", "FAILED", "PARTIAL_SUCCESS"):
            if status != "SUCCEEDED":
                raise RuntimeError(f"Textract job did not succeed. Status: {status}")
            return
        time.sleep(poll_seconds)


def get_all_pages(textract_client, job_id: str) -> List[Dict]:
    pages = []
    next_token = None
    while True:
        if next_token:
            res = textract_client.get_document_analysis(JobId=job_id, NextToken=next_token)
        else:
            res = textract_client.get_document_analysis(JobId=job_id)
        pages.append(res)
        next_token = res.get("NextToken")
        if not next_token:
            break
    return pages


def build_block_map(blocks: List[Dict]) -> Dict[str, Dict]:
    return {b["Id"]: b for b in blocks}


def get_text_for_cell(block_map: Dict[str, Dict], cell_block: Dict) -> str:
    texts: List[str] = []
    for rel in cell_block.get("Relationships", []) or []:
        if rel.get("Type") == "CHILD":
            for cid in rel.get("Ids", []):
                child = block_map.get(cid)
                if not child:
                    continue
                if child.get("BlockType") == "WORD":
                    texts.append(child.get("Text", ""))
                elif child.get("BlockType") == "SELECTION_ELEMENT":
                    if child.get("SelectionStatus") == "SELECTED":
                        texts.append("X")
    return " ".join(t for t in texts if t).strip()


def extract_tables_from_page(blocks: List[Dict]) -> List[pd.DataFrame]:
    block_map = build_block_map(blocks)
    tables = [b for b in blocks if b.get("BlockType") == "TABLE"]
    dataframes: List[pd.DataFrame] = []
    for table in tables:
        # find all cells for this table
        cells = []
        for rel in table.get("Relationships", []) or []:
            if rel.get("Type") == "CHILD":
                for cid in rel.get("Ids", []):
                    child = block_map.get(cid)
                    if child and child.get("BlockType") == "CELL":
                        cells.append(child)

        if not cells:
            continue

        max_row = max(c.get("RowIndex", 0) for c in cells)
        max_col = max(c.get("ColumnIndex", 0) for c in cells)
        grid: List[List[str]] = [["" for _ in range(max_col)] for _ in range(max_row)]

        for cell in cells:
            r = cell.get("RowIndex", 1) - 1
            c = cell.get("ColumnIndex", 1) - 1
            txt = get_text_for_cell(block_map, cell)
            # handle merged cells by placing text once if empty
            if not grid[r][c]:
                grid[r][c] = txt
            else:
                grid[r][c] = f"{grid[r][c]} {txt}".strip()

        df = pd.DataFrame(grid)
        dataframes.append(df)
    return dataframes


def save_tables(tables: List[pd.DataFrame], output_dir: str, base_name: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    saved_paths: List[str] = []
    for i, df in enumerate(tables, start=1):
        csv_path = os.path.join(output_dir, f"{base_name}_table_{i}.csv")
        xlsx_path = os.path.join(output_dir, f"{base_name}_table_{i}.xlsx")
        df.to_csv(csv_path, index=False, header=False)
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, header=False)
        saved_paths.extend([csv_path, xlsx_path])
    return saved_paths


def run(pdf_path: str, bucket: str, output_dir: str, aws_config_path: str) -> List[str]:
    s3, textract = get_boto_clients(aws_config_path)
    s3_key = upload_to_s3(s3, pdf_path, bucket)
    job_id = start_textract_job(textract, bucket, s3_key)
    wait_for_job(textract, job_id)
    pages = get_all_pages(textract, job_id)

    all_tables: List[pd.DataFrame] = []
    for page in pages:
        page_tables = extract_tables_from_page(page.get("Blocks", []) or [])
        all_tables.extend(page_tables)

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    return save_tables(all_tables, output_dir, base_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract tables from scanned PDFs using AWS Textract")
    parser.add_argument("pdf", help="Path to local PDF file")
    parser.add_argument("--bucket", required=True, help="S3 bucket to upload the PDF")
    parser.add_argument("--out", default="outputs", help="Directory to write CSV/Excel tables")
    parser.add_argument(
        "--aws-config",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "aws_config.json"),
        help="Path to aws_config.json with credentials",
    )
    args = parser.parse_args()

    saved = run(args.pdf, args.bucket, args.out, args.aws_config)
    print("Saved:")
    for p in saved:
        print(p)


if __name__ == "__main__":
    main()


