# Pharma Bill Extractor (Python + OCR + NLP + PyQt5)

A desktop application that automatically extracts medicine details, metadata, totals, and line items from **pharma bills / medical invoices** in PDF format.  
Supports both **text-based PDFs** and **scanned bills** using OCR (Tesseract).

The application converts input PDFs → structured CSV files.

## Features
- Extracts text from PDFs (text + scanned)
- OCR using Tesseract
- Detects bill type (retail, hospital, insurance)
- Extracts metadata (invoice, date, totals, pharmacy, etc.)
- Extracts medicine line items
- CSV export
- Multi-file batch processing
- PyQt5 GUI with progress bar & logging

## Installation
```
pip install -r requirements.txt
```

Install Tesseract OCR and update path in code.

## Run
```
python main.py
```

## Author
Muhammed Iqbal  
Email: iqbalalivia890@gmail.com
