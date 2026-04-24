# Receipt Generator — מחולל קבלות

A Python receipt generator for Israeli **עוסק פטור** businesses.  
Generates professional, numbered Hebrew receipt PDFs with zero LaTeX required.

**Stack:** Python · Jinja2 (HTML template) · WeasyPrint (HTML → PDF)

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

> **macOS note:** WeasyPrint needs Pango for text rendering. If the install fails, run:
> ```bash
> brew install pango
> pip install -r requirements.txt
> ```

### 2. Create your config file

```bash
cp config.example.json config.json
```

Edit `config.json` with your business details:

```json
{
  "business_name":    "שם העסק שלי",
  "business_address": "רחוב הרצל 1, תל אביב",
  "business_phone":   "050-1234567",
  "business_id":      "123456789",
  "last_receipt_number": 0
}
```

`last_receipt_number` is auto-incremented every time you generate a receipt.

---

## Usage

### Interactive mode
Asks you for everything step-by-step:
```bash
python generate_receipt.py
```

### CLI mode
Fully scriptable — useful for automation or aliases:
```bash
python generate_receipt.py \
    --recipient "ישראל ישראלי" \
    --address "רחוב ויצמן 5, ירושלים" \
    --items "פיתוח אתר אינטרנט:5000" "ייעוץ:800" \
    --cash 5800
```

### With cheque payment
Cheque format: `number:bank:account:date:amount_nis`
```bash
python generate_receipt.py \
    --recipient "חברת ABC בע\"מ" \
    --items "שירותי תוכנה:12000" \
    --cash 2000 \
    --checks "123456:הפועלים:9876543:30/04/2025:10000"
```

### Other options
```bash
# Backdate a receipt
python generate_receipt.py --date 15/03/2025 ...

# Reprint without changing the counter
python generate_receipt.py --no-increment ...
```

---

## Output

PDFs are saved in `output/` as `receipt_0001.pdf`, `receipt_0002.pdf`, etc.  
The PDF opens automatically after generation.

---

## File structure

```
receipt-generator/
├── generate_receipt.py      # Main script
├── config.json              # Your business details + counter (gitignored)
├── config.example.json      # Template — copy to config.json
├── requirements.txt         # pip dependencies
├── template/
│   └── receipt.html         # Jinja2 HTML template (edit to customise layout)
├── output/                  # Generated PDFs (gitignored)
└── README.md
```

---

## Customising the receipt layout

Open `template/receipt.html` in any text editor or browser to preview and edit.  
The `<style>` block at the top controls all fonts, spacing, and table widths.  
The template uses standard Jinja2 syntax (`{{ variable }}`, `{% for %}`, etc.).
