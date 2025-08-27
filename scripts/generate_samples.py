import os
from pathlib import Path
import random
from datetime import date, timedelta
from typing import List

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas


SAMPLES = [
    [
        "Dipayans Claims Center",
        "Reference: Claim No: ABC-12345",
        "Claimant: John A. Doe",
        "Reported Date: 03/12/2024",
        "Notes: vehicle rear-ended at intersection.",
    ],
    [
        "INTERNAL MEMO",
        "ID 9981",
        "claim# ZX9-88/776",
        "Name - Jane Smith",
        "Date 12-04-2023",
    ],
    [
        "Loss Summary",
        "The claim number is 2024-XY-00991 for insured Mark O'Neil",
        "The accident occurred on March 5, 2024",
    ],
]


def _draw_paragraph(c: canvas.Canvas, lines: List[str], left: int, top: int, leading: int = 16):
    y = top
    for line in lines:
        c.drawString(left, y, line)
        y -= leading


def _wrap_text(c: canvas.Canvas, text: str, max_width: int, font_name: str = "Helvetica", font_size: int = 11) -> List[str]:
    c.setFont(font_name, font_size)
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if c.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped_paragraph(c: canvas.Canvas, text_lines: List[str], left: int, top: int, max_width: int, leading: int = 16, font_name: str = "Helvetica", font_size: int = 11):
    y = top
    c.setFont(font_name, font_size)
    for line in text_lines:
        wrapped = _wrap_text(c, line, max_width, font_name=font_name, font_size=font_size)
        for seg in wrapped:
            c.drawString(left, y, seg)
            y -= leading
        y -= 4  # small gap between numbered items


def generate_instruction_pdf(out_dir: str) -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    file_path = Path(out_dir) / "non_nw_instructions_sample.pdf"
    c = canvas.Canvas(str(file_path), pagesize=LETTER)
    width, height = LETTER

    # Page 1 content
    page1_items = [
        "Page 1",
        "",
        "1. Open the email with instructions and specifically looking for a call out on account information for items such as policy effective date, limits of business, and who the report will be returned to (finding Major issues/deductibles errors info you will need to be entered into the non-NW template).",
        "",
        "2. Right click and rename the template with account extension (Non-NW Marketing).",
        "",
        "3. Open the file and complete cells B1, B2, E1 and E2. Be sure to use the CURRENT Effective date in cell B1. For WC be sure to do this on the WC tab & the Ind Tab.",
        "",
        "4. Now begin to complete loss data from loss runs provided starting with external company Named, Carrier, ROW As, Date claim number D5, Expenses date C5, and payments incurred Bal Member Paid Amount E5, etc. Expenses are separated from those DO NOT INCLUDE ANY EXPENSE RESERVES. In F5 this where an reserves are totaled excluding expense reserves.",
        "",
        "5. Continue to complete this file until all claims have been entered from ALL PDFs.",
        "",
        "6. Once all claims are entered save your file.",
        "",
        "7. On the Non NW Losses Tab copy all the entries on the date of loss column C5 and down. Paste this data into the next tab Losses Check B3 and down.",
        "",
        "8. In cells E2 and E3 - double check this data and verify it has come over correctly. If there is a deductible it should be showing in E3. If not it will default to 0. The effective date will now show as the date the account will renew. So it will be the date on the first tab plus one year.",
    ]

    left_margin = 72
    top_margin = height - 72
    max_width = int(width - 2 * left_margin)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_margin, top_margin, "Page 1")
    _draw_wrapped_paragraph(c, page1_items[2:], left=left_margin, top=top_margin - 24, max_width=max_width, leading=16)
    c.showPage()

    # Page 2 content
    page2_items = [
        "Page 2",
        "",
        "9. Back on the Non NW Losses tab copy all the data showing in cell from H5 and down, paste this as values in cells G7 and down on the Losses Check tab.",
        "",
        "10. Return to the Non NW Losses tab and grab the data I5 and paste as values down on Losses Check tab.",
        "",
        "11. Again go back to the Non NW Losses tab, copy data in K5 and down and paste into E7.",
        "",
        "12. Save the file",
    ]
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_margin, top_margin, "Page 2")
    _draw_wrapped_paragraph(c, page2_items[2:], left=left_margin, top=top_margin - 24, max_width=max_width, leading=16)
    c.showPage()
    c.save()
    print(f"Created {file_path}")


def generate_samples(out_dir: str) -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    for idx, lines in enumerate(SAMPLES, start=1):
        file_path = Path(out_dir) / f"sample_claim_variation_{idx}.pdf"
        c = canvas.Canvas(str(file_path), pagesize=LETTER)
        width, height = LETTER
        _draw_paragraph(c, lines, left=72, top=height - 72)
        c.showPage()
        c.save()
        print(f"Created {file_path}")


def _random_claim_number(rng: random.Random, prefix_pool=None, seq=None) -> str:
    prefix_pool = prefix_pool or ["ABC", "XYZ", "NW", "ZX9", "LMN", "QRS"]
    prefix = rng.choice(prefix_pool)
    if seq is None:
        seq = rng.randint(10000, 99999)
    suffix = rng.choice(["", f"-{rng.randint(10,99)}", f"/{rng.randint(100,999)}"])
    return f"{prefix}-{seq}{suffix}"


def _random_reason(rng: random.Random) -> str:
    reasons = [
        "Auto collision",
        "Water damage",
        "Fire damage",
        "Theft",
        "Hail storm",
        "Slip and fall",
        "Wind damage",
        "Liability claim",
        "Glass replacement",
        "Property vandalism",
    ]
    return rng.choice(reasons)


def _random_amount(rng: random.Random) -> float:
    # Amounts between 100 and 50,000 with two decimals
    return round(rng.uniform(100, 50000), 2)


def _random_date(rng: random.Random, years_back: int = 5) -> str:
    start = date.today() - timedelta(days=365 * years_back)
    delta_days = rng.randint(0, 365 * years_back)
    d = start + timedelta(days=delta_days)
    return d.strftime("%m/%d/%Y")


def generate_bulk_claims_pdfs(out_dir: str, num_pdfs: int = 1, num_claims: int = 100, duplicate_ratio: float = 0.2, seed: int = 42) -> None:
    """
    Generate one or more PDFs; each contains num_claims claims with fields:
    - Claim Number (with duplicates possible across PDFs)
    - Claim Amount
    - Claim Reason
    - Date of Loss

    duplicate_ratio controls the fraction of claims that will reuse an existing
    base claim number across the entire batch to simulate duplicates.
    """
    rng = random.Random(seed)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Prepare a base pool of claim numbers to create duplicates from
    unique_count = max(1, int(num_claims * (1.0 - duplicate_ratio)))
    base_seqs = [rng.randint(10000, 99999) for _ in range(unique_count)]
    base_numbers = [_random_claim_number(rng, seq=seq) for seq in base_seqs]

    templates = [
        "Claim# {claim_no} noted with amount ${amount:,.2f}. Reason: {reason}. Date of loss: {loss_date}.",
        "On {loss_date}, claim number {claim_no} was reported for {reason}; amount ${amount:,.2f}.",
        "Claim {claim_no}: {reason} — incurred ${amount:,.2f}; DoL {loss_date}.",
        "Reported DoL {loss_date}. Ref {claim_no}. Cause: {reason}. Indemnity ${amount:,.2f}.",
        "Reference {claim_no} — {reason}. Total ${amount:,.2f}. Loss date {loss_date}.",
        "For claim id {claim_no}, loss {loss_date}, reason {reason}, amount ${amount:,.2f}.",
    ]

    for i in range(1, num_pdfs + 1):
        file_path = Path(out_dir) / f"bulk_claims_{i}.pdf"
        c = canvas.Canvas(str(file_path), pagesize=LETTER)
        width, height = LETTER

        left_margin = 54
        right_margin = 54
        top_margin = height - 54
        bottom_margin = 54
        line_height = 14

        # Header
        def new_page(page_num: int):
            c.setFont("Helvetica-Bold", 12)
            c.drawString(left_margin, top_margin, f"Bulk Claims Sample - File {i} - Page {page_num}")
            c.setFont("Helvetica", 10)
            c.drawString(left_margin, top_margin - 18, "Columns: Claim Number | Amount | Reason | Date of Loss")

        page_num = 1
        new_page(page_num)
        y = top_margin - 36

        for n in range(num_claims):
            # Choose a claim number: duplicate from base or new unique
            if base_numbers and rng.random() < duplicate_ratio:
                claim_no = rng.choice(base_numbers)
            else:
                claim_no = _random_claim_number(rng)

            amount = _random_amount(rng)
            reason = _random_reason(rng)
            loss_date = _random_date(rng)

            # Unstructured narrative text (vary wording/order)
            template = rng.choice(templates)
            paragraph = template.format(claim_no=claim_no, amount=amount, reason=reason, loss_date=loss_date)

            # Wrap and draw, then add a blank line between claims as delimiter
            max_width = int(width - left_margin - right_margin)
            wrapped_lines = _wrap_text(c, paragraph, max_width, font_name="Helvetica", font_size=10)
            c.setFont("Helvetica", 10)
            for seg in wrapped_lines:
                c.drawString(left_margin, y, seg)
                y -= line_height
                if y < bottom_margin:
                    c.showPage()
                    page_num += 1
                    new_page(page_num)
                    y = top_margin - 36
            # delimiter line between claims
            y -= line_height

            if y < bottom_margin:
                c.showPage()
                page_num += 1
                new_page(page_num)
                y = top_margin - 36

        c.showPage()
        c.save()
        print(f"Created {file_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate unstructured sample claim PDFs")
    parser.add_argument("--out", dest="out", default="samples", help="Output directory")
    parser.add_argument("--instructions", dest="instructions", action="store_true", help="Also generate the two-page instructions sample PDF")
    parser.add_argument("--bulk", dest="bulk", action="store_true", help="Generate bulk claims PDF(s)")
    parser.add_argument("--bulk-pdfs", dest="bulk_pdfs", type=int, default=1, help="Number of bulk PDFs to create")
    parser.add_argument("--bulk-claims", dest="bulk_claims", type=int, default=50, help="Claims per bulk PDF")
    parser.add_argument("--dup-ratio", dest="dup_ratio", type=float, default=0.2, help="Duplicate ratio across PDFs (0.0-1.0)")
    parser.add_argument("--seed", dest="seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()
    generate_samples(args.out)
    if args.instructions:
        generate_instruction_pdf(args.out)
    if args.bulk:
        generate_bulk_claims_pdfs(args.out, num_pdfs=args.bulk_pdfs, num_claims=args.bulk_claims, duplicate_ratio=args.dup_ratio, seed=args.seed)



