# Pharma Bill Extractor (Python + OCR + NLP + PyQt5)

A desktop application that automatically extracts medicine details, metadata, totals, and line items from **pharma bills / medical invoices** in PDF format.  
Supports both **text-based PDFs** and **scanned bills** using OCR (Tesseract).

The application converts input PDFs → structured CSV files.

---

## 🚀 Features

- Extracts text from PDFs (text-based + scanned)
- OCR powered by Tesseract
- Detects bill type (retail, hospital, insurance)
- Extracts metadata:
  - Invoice ID  
  - Date  
  - Total amount  
  - Pharmacy name  
  - Customer details  
- Extracts medicine line items:
  - Name  
  - Quantity  
  - Unit price  
  - Total price  
- Filters valid pharmaceutical items using keyword-based NLP rules
- Generates clean CSV files for each PDF
- Multi-file upload support
- Progress bar + live log updates
- Threaded processing (UI does not freeze)
- Simple and clean PyQt5 interface

---

## 🛠️ Tech Stack

- **Python 3.9+**
- **PyQt5** (desktop UI)
- **pdfplumber** (PDF parsing)
- **Pillow (PIL)** (image handling)
- **pytesseract** (OCR engine)
- **pandas**
- **regex** (pattern extraction)
- **datetime**
- **CSV writer**

---

## 📦 Installation

### 1️⃣ Clone the repository
