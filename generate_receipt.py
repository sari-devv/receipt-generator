"""
generate_receipt.py
===================
Generate a numbered Hebrew receipt PDF for an Israeli עוסק פטור business.

Usage:
    python generate_receipt.py                          # interactive mode
    python generate_receipt.py --help                   # show all options
    python generate_receipt.py \\
        --recipient "ישראל ישראלי" \\
        --address "רחוב הרצל 1, תל אביב" \\
        --items "פיתוח אתר אינטרנט:5000" "ייעוץ:800" \\
        --cash 5800

The script:
  1. Reads config.json for business details & last receipt number.
  2. Increments the receipt number and saves it back to config.json.
  3. Renders template/receipt.html via Jinja2.
  4. Converts the HTML to PDF using weasyprint.
  5. Saves the PDF to output/receipt_NNNN.pdf and opens it.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("ERROR: jinja2 not installed. Run: pip install jinja2 weasyprint")
    sys.exit(1)

try:
    from weasyprint import HTML as WeasyprintHTML
except ImportError:
    print("ERROR: weasyprint not installed. Run: pip install jinja2 weasyprint")
    sys.exit(1)


# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent.resolve()
CONFIG_PATH   = SCRIPT_DIR / "config.json"
TEMPLATE_DIR  = SCRIPT_DIR / "template"
OUTPUT_DIR    = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Config helpers ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"ERROR: config.json not found at {CONFIG_PATH}")
        print("Copy config.example.json to config.json and fill in your details.")
        sys.exit(1)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── Amount helpers ─────────────────────────────────────────────────────────────

def parse_amount(amount_str: str) -> int:
    """Parse a NIS amount string ('5000', '500.50', '1,200') → agorot (int)."""
    cleaned = str(amount_str).replace(",", "").strip()
    try:
        return round(float(cleaned) * 100)
    except ValueError:
        raise ValueError(f"Invalid amount: '{amount_str}'")


def agorot_to_parts(total_agorot: int) -> tuple[str, str]:
    """Split agorot total → (nis_str, agorot_str) for display."""
    nis = total_agorot // 100
    ag  = total_agorot % 100
    return f"{nis:,}", f"{ag:02d}"


def parse_item(item_str: str) -> dict:
    """Parse 'description:amount_nis' → dict with description + amount_agorot."""
    parts = item_str.rsplit(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Item format must be 'description:amount' — got: '{item_str}'")
    return {"description": parts[0].strip(), "amount_agorot": parse_amount(parts[1])}


# ── Date helper ────────────────────────────────────────────────────────────────

def today_str(d: date | None = None) -> str:
    return (d or date.today()).strftime("%d/%m/%Y")


# ── Template rendering ─────────────────────────────────────────────────────────

def render_receipt(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("receipt.html")
    return tmpl.render(**context)


# ── Build template context ─────────────────────────────────────────────────────

def build_context(
    cfg: dict,
    receipt_number: int,
    receipt_date: str,
    recipient: str,
    address: str,
    items: list[dict],
    cash_agorot: int,
    checks: list[dict],
) -> dict:
    total_agorot   = sum(i["amount_agorot"] for i in items)
    total_nis, total_ag = agorot_to_parts(total_agorot)
    cash_nis, cash_ag   = agorot_to_parts(cash_agorot)

    # Enrich each item with display strings
    item_rows = []
    for item in items:
        nis, ag = agorot_to_parts(item["amount_agorot"])
        item_rows.append({"description": item["description"], "nis": nis, "ag": ag})

    # Enrich each cheque with display strings
    check_rows = []
    for chk in checks:
        nis, ag = agorot_to_parts(chk["amount_agorot"])
        check_rows.append({**chk, "nis": nis, "ag": ag})

    # Pad items to at least 6 rows for the classic receipt look
    empty_rows = max(6 - len(item_rows), 0)

    # Cash display: show amount if non-zero, else blank
    cash_display = f"₪{cash_nis}" if cash_agorot else ""

    return {
        # Business
        "business_name":    cfg["business_name"],
        "business_address": cfg["business_address"],
        "business_phone":   cfg["business_phone"],
        "business_id":      cfg["business_id"],
        # Receipt meta
        "receipt_number":   receipt_number,
        "receipt_date":     receipt_date,
        # Recipient
        "recipient_name":    recipient,
        "recipient_address": address,
        # Items
        "items":       item_rows,
        "empty_rows":  empty_rows,
        # Totals
        "total_nis": total_nis,
        "total_ag":  total_ag,
        # Payment
        "cash_nis":     cash_nis,
        "cash_ag":      cash_ag,
        "cash_display": cash_display,
        "checks":       check_rows,
    }


# ── Interactive mode ───────────────────────────────────────────────────────────

def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{label}{suffix}: ").strip()
    return val if val else default


def interactive_mode() -> tuple[str, str, list[dict], int, list[dict]]:
    print("\n── Receipt Details ─────────────────────────────────────────")
    recipient = prompt("Recipient Name (לכבוד)")
    address   = prompt("Recipient Address (כתובת)", default="")

    print("\nEnter items (leave description empty to finish):")
    items = []
    while True:
        desc = prompt("  Item Description (or ENTER to finish)")
        if not desc:
            break
        amount_str = prompt(f"  Amount in NIS for '{desc}'")
        items.append({"description": desc, "amount_agorot": parse_amount(amount_str)})

    if not items:
        print("ERROR: Must have at least one item.")
        sys.exit(1)

    total_agorot = sum(i["amount_agorot"] for i in items)
    total_nis, _ = agorot_to_parts(total_agorot)
    print(f"\nTotal: ₪{total_nis}")

    cash_str   = prompt("Cash Payment (NIS)", default=total_nis.replace(",", ""))
    cash_agorot = parse_amount(cash_str)

    checks = []
    remaining = total_agorot - cash_agorot
    if remaining > 0:
        print("Enter cheque details (leave cheque number empty to finish):")
        while remaining > 0:
            num = prompt("  Cheque Number")
            if not num:
                break
            bank     = prompt("  Bank Name")
            account  = prompt("  Account Number")
            chk_date = prompt("  Cheque Date (DD/MM/YYYY)", default=today_str())
            rem_nis, _ = agorot_to_parts(remaining)
            chk_str  = prompt(f"  Cheque Amount (NIS)", default=rem_nis.replace(",", ""))
            chk_agorot = parse_amount(chk_str)
            checks.append({
                "number": num, "bank": bank, "account": account,
                "date_str": chk_date, "amount_agorot": chk_agorot,
            })
            remaining -= chk_agorot

    return recipient, address, items, cash_agorot, checks


# ── CLI args ───────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a numbered Hebrew receipt PDF (עוסק פטור).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python generate_receipt.py

  # Full CLI mode
  python generate_receipt.py \\
      --recipient "חברת ABC בע\\"מ" \\
      --address "דרך מנחם בגין 125, תל אביב" \\
      --items "פיתוח אתר:5000" "ייעוץ חודשי:800" \\
      --cash 5800

  # With cheque payment
  python generate_receipt.py \\
      --recipient "לקוח לדוגמה" \\
      --items "שירותי תוכנה:12000" \\
      --cash 2000 \\
      --checks "123456:הפועלים:9876543:30/04/2025:10000"

  # Reprint without incrementing counter
  python generate_receipt.py --no-increment ...

  # Backdate
  python generate_receipt.py --date 15/03/2025 ...
        """,
    )
    parser.add_argument("--recipient", "-r", help="Recipient name (לכבוד)")
    parser.add_argument("--address",   "-a", help="Recipient address (כתובת)", default="")
    parser.add_argument("--items",     "-i", nargs="+",
                        help="Line items as 'description:amount_nis'")
    parser.add_argument("--cash",      "-c", type=str, default=None,
                        help="Cash payment in NIS (default: full total)")
    parser.add_argument("--checks",    nargs="+",
                        help="Cheques as 'number:bank:account:date:amount_nis'")
    parser.add_argument("--date",      "-d", default=None,
                        help="Receipt date DD/MM/YYYY (default: today)")
    parser.add_argument("--no-increment", action="store_true",
                        help="Don't increment the receipt counter (reprint)")
    return parser.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    args   = parse_args()
    cfg    = load_config()

    receipt_date   = args.date or today_str()
    current_number = cfg.get("last_receipt_number", 0)
    receipt_number = current_number if args.no_increment else current_number + 1

    # ── Gather receipt data ────────────────────────────────────────────────
    if args.recipient:
        recipient = args.recipient
        address   = args.address
        items     = [parse_item(i) for i in (args.items or [])]

        total_agorot = sum(i["amount_agorot"] for i in items)
        cash_agorot  = parse_amount(args.cash) if args.cash else total_agorot

        checks = []
        for chk_str in (args.checks or []):
            parts = chk_str.split(":")
            if len(parts) != 5:
                raise ValueError(
                    "Cheque format: 'number:bank:account:date:amount_nis'"
                )
            num, bank, account, chk_date, chk_amount = parts
            checks.append({
                "number": num, "bank": bank, "account": account,
                "date_str": chk_date, "amount_agorot": parse_amount(chk_amount),
            })
    else:
        recipient, address, items, cash_agorot, checks = interactive_mode()

    if not items:
        print("ERROR: At least one item is required.")
        sys.exit(1)

    # ── Render template ────────────────────────────────────────────────────
    context = build_context(
        cfg, receipt_number, receipt_date,
        recipient, address, items, cash_agorot, checks,
    )
    html_content = render_receipt(context)

    # ── Generate PDF ───────────────────────────────────────────────────────
    pdf_path = OUTPUT_DIR / f"receipt_{receipt_number:04d}.pdf"
    print(f"\nGenerating receipt #{receipt_number}…")

    WeasyprintHTML(
        string=html_content,
        base_url=str(TEMPLATE_DIR),   # allows relative asset paths in template
    ).write_pdf(str(pdf_path))

    print(f"✓  PDF saved: {pdf_path}")

    # ── Update counter ─────────────────────────────────────────────────────
    if not args.no_increment:
        cfg["last_receipt_number"] = receipt_number
        save_config(cfg)
        print(f"✓  Receipt counter updated → {receipt_number}")

    # ── Open the PDF ───────────────────────────────────────────────────────
    if sys.platform == "darwin":
        subprocess.run(["open", str(pdf_path)])
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(pdf_path)])
    elif sys.platform == "win32":
        os.startfile(str(pdf_path))


if __name__ == "__main__":
    main()
