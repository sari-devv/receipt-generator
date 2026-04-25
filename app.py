import json
import os
import sys
from datetime import date
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify

# ── Path setup ─────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.json"
OUTPUT_DIR  = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR = SCRIPT_DIR / "template"

# ── Import core logic from generate_receipt ────────────────────────────────────
sys.path.insert(0, str(SCRIPT_DIR))
from generate_receipt import (
    agorot_to_parts,
    build_context,
    load_config,
    parse_amount,
    render_receipt,
    save_config,
    today_str,
)
from weasyprint import HTML as WeasyprintHTML

app = Flask(__name__)

@app.route("/")
def index():
    cfg = load_config()
    next_num = cfg.get("last_receipt_number", 0) + 1
    return render_template("index.html", cfg=cfg, next_num=next_num, today=today_str())

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.json
        cfg = load_config()

        recipient = data.get("recipient", "").strip()
        if not recipient:
            return jsonify({"error": "שם המקבל הוא שדה חובה"}), 400
        
        address = data.get("address", "").strip()
        receipt_date = data.get("date", "").strip() or today_str()
        
        no_increment = data.get("no_increment", False)
        current_num = cfg.get("last_receipt_number", 0)
        receipt_number = current_num if no_increment else current_num + 1

        items_data = data.get("items", [])
        items = []
        for item in items_data:
            desc = item.get("description", "").strip()
            amt = item.get("amount", "").strip()
            if desc and amt:
                items.append({
                    "description": desc,
                    "amount_agorot": parse_amount(amt)
                })

        if not items:
            return jsonify({"error": "יש להזין לפחות פריט אחד עם תיאור וסכום"}), 400

        total_agorot = sum(i["amount_agorot"] for i in items)

        cash_str = data.get("cash", "").strip()
        cash_agorot = parse_amount(cash_str) if cash_str else total_agorot

        checks_data = data.get("checks", [])
        checks = []
        for chk in checks_data:
            num = chk.get("number", "").strip()
            bank = chk.get("bank", "").strip()
            acct = chk.get("account", "").strip()
            chkdate = chk.get("date", "").strip() or today_str()
            amt_str = chk.get("amount", "").strip()

            if any([num, bank, acct, amt_str]):
                if not amt_str:
                     return jsonify({"error": f"חסר סכום לשיק מספר {num or '?'}"}), 400
                checks.append({
                    "number": num, "bank": bank, "account": acct,
                    "date_str": chkdate, "amount_agorot": parse_amount(amt_str),
                })

        transfers_data = data.get("transfers", [])
        transfers = []
        for t in transfers_data:
            ref = t.get("ref", "").strip()
            bank = t.get("bank", "").strip()
            acct = t.get("account", "").strip()
            tdate = t.get("date", "").strip() or today_str()
            amt_str = t.get("amount", "").strip()

            if any([ref, bank, acct, amt_str]):
                if not amt_str:
                     return jsonify({"error": f"חסר סכום להעברה {ref or '?'}"}), 400
                transfers.append({
                    "ref": ref, "bank": bank, "account": acct,
                    "date_str": tdate, "amount_agorot": parse_amount(amt_str),
                })

        # Build context & render
        context = build_context(
            cfg, receipt_number, receipt_date,
            recipient, address, items, cash_agorot, checks, transfers,
        )
        html_content = render_receipt(context)

        # Save PDF
        pdf_filename = f"receipt_{receipt_number:04d}.pdf"
        pdf_path = OUTPUT_DIR / pdf_filename
        WeasyprintHTML(
            string=html_content,
            base_url=str(TEMPLATE_DIR),
        ).write_pdf(str(pdf_path))

        # Update counter
        if not no_increment:
            cfg["last_receipt_number"] = receipt_number
            save_config(cfg)

        return jsonify({
            "success": True, 
            "message": f"קבלה #{receipt_number} נוצרה בהצלחה",
            "pdf_url": f"/download/{pdf_filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download/<filename>")
def download(filename):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return send_file(file_path, as_attachment=True)
    return "File not found", 404

import socket

def find_free_port(start_port=5000, max_port=5010):
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return None

if __name__ == "__main__":
    # Find an available port starting from 5000
    port = find_free_port()
    if port:
        print(f"Starting server on port {port}...")
        app.run(debug=True, host="0.0.0.0", port=port)
    else:
        print("Could not find an open port between 5000 and 5010. Please free up a port and try again.")
