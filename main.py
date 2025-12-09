import os
import sys
import csv
import re
import pdfplumber
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import pandas as pd
from PIL import Image
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QListWidget, QProgressBar, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Configuration
PHARMA_KEYWORDS = ["tab", "cap", "inj", "cream", "syrup", "drops", "mg", "ml", "bottle", "gel", "patch", "sachet"]
BILL_PATTERNS = {
    "retail": ["rx:", "prescription", "dispensed by"],
    "hospital": ["inpatient", "ward", "discharge summary"],
    "insurance": ["claim no", "policy number", "co-pay"]
}

class PharmaBillProcessor:
    def __init__(self):
        self.bill_type = "standard"
    
    def extract_text_from_pdf(self, pdf_path):
        """Extracts text from PDF, handling both text-based and scanned documents"""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    # Try text extraction first
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    else:
                        # Fallback to OCR for image-based pages
                        img = page.to_image(resolution=300).original
                        if not isinstance(img, Image.Image):
                            img = Image.fromarray(img)
                        page_text = pytesseract.image_to_string(img)
                        text += page_text + "\n"
        except Exception as e:
            print(f"Error processing PDF: {e}")
        return text

    def detect_bill_type(self, text):
        """Identifies the bill pattern for specialized processing"""
        text_lower = text.lower()
        for bill_type, keywords in BILL_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                return bill_type
        return "standard"

    def extract_metadata(self, text):
        """Extracts common metadata from bill text"""
        metadata = {
            "invoice_id": "",
            "date": "",
            "pharmacy": "",
            "customer": "",
            "total": "",
            "subtotal": "",
            "tax": ""
        }
        
        # Extract invoice ID (common patterns)
        invoice_patterns = [
            r"Invoice\s*[:#]?\s*(\w+\d+)",
            r"Bill\s*No[:.]?\s*(\w+\d+)",
            r"INV[-]?(\d+)"
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["invoice_id"] = match.group(1)
                break
        
        # Extract date (common formats)
        date_patterns = [
            r"(\d{2}[/-]\d{2}[/-]\d{4})",  # DD/MM/YYYY
            r"(\d{4}[/-]\d{2}[/-]\d{2})",  # YYYY/MM/DD
            r"(\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})"  # 01 Jan 2023
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    # Try to parse and standardize the date
                    date_str = match.group(1)
                    for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            metadata["date"] = dt.strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            continue
                    if metadata["date"]:
                        break
                except:
                    continue
        
        # Extract totals
        total_patterns = [
            r"Total\s*[:]?\s*([\d,]+\.\d{2})",
            r"Amount\s*Payable\s*[:]?\s*([\d,]+\.\d{2})",
            r"Grand\s*Total\s*[:]?\s*([\d,]+\.\d{2})"
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["total"] = match.group(1).replace(",", "")
                break
        
        return metadata

    def extract_line_items(self, text):
        """Extracts medicine line items from bill text"""
        items = []
        lines = text.split('\n')
        
        # Patterns for medicine lines
        medicine_patterns = [
            # Pattern: Name, Strength, Form, Qty, Price
            r"([\w\s]+)\s+(\d+(?:\.\d+)?\s*(?:mg|g|ml)?)\s+(\w+)\s+(\d+)\s+([\d,]+\.\d{2})",
            # Pattern: Name, Qty x Price = Total
            r"([\w\s]+)\s+(\d+)\s*x\s*([\d,]+\.\d{2})\s*=\s*([\d,]+\.\d{2})",
            # Simple pattern: Name, Qty, Price
            r"([\w\s]+)\s+(\d+)\s+([\d,]+\.\d{2})"
        ]
        
        for line in lines:
            # Skip lines that are clearly not medicine items
            if any(word in line.lower() for word in ["total", "subtotal", "tax", "discount"]):
                continue
                
            for pattern in medicine_patterns:
                match = re.search(pattern, line)
                if match:
                    groups = match.groups()
                    item = {
                        "name": groups[0].strip(),
                        "quantity": groups[1] if len(groups) > 1 else "",
                        "price": groups[2] if len(groups) > 2 else "",
                        "total": groups[3] if len(groups) > 3 else ""
                    }
                    
                    # Filter non-pharma items
                    if self.is_pharma_item(item["name"]):
                        items.append(item)
                    break
        
        return items

    def is_pharma_item(self, item_name):
        """Determines if an item is pharmaceutical based on keywords"""
        name_lower = item_name.lower()
        return any(kw in name_lower for kw in PHARMA_KEYWORDS)

    def process_bill(self, pdf_path):
        """Main processing function for a single bill"""
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            return None, "Failed to extract text from PDF"
        
        self.bill_type = self.detect_bill_type(text)
        metadata = self.extract_metadata(text)
        line_items = self.extract_line_items(text)
        
        if not line_items:
            return None, "No pharmaceutical items found in the bill"
        
        return {
            "metadata": metadata,
            "line_items": line_items,
            "bill_type": self.bill_type
        }, ""

    def generate_csv(self, data, output_path):
        """Generates structured CSV output"""
        metadata = data["metadata"]
        line_items = data["line_items"]
        
        # Create directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write metadata
            writer.writerow(["InvoiceID", "PharmacyName", "Date", "Customer", "Total", "BillType"])
            writer.writerow([
                metadata.get("invoice_id", ""),
                metadata.get("pharmacy", ""),
                metadata.get("date", ""),
                metadata.get("customer", ""),
                metadata.get("total", ""),
                data.get("bill_type", "standard")
            ])
            
            # Blank row
            writer.writerow([])
            
            # Write items header
            writer.writerow(["MedicineName", "Quantity", "UnitPrice", "TotalPrice"])
            
            # Write line items
            for item in line_items:
                writer.writerow([
                    item.get("name", ""),
                    item.get("quantity", ""),
                    item.get("price", ""),
                    item.get("total", "")
                ])
        
        return output_path


class ProcessingThread(QThread):
    """Thread for processing bills in the background"""
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    result = pyqtSignal(str, str)  # (input_path, output_path)
    error = pyqtSignal(str, str)   # (input_path, error_message)
    completed = pyqtSignal()

    def __init__(self, input_files, output_dir):
        super().__init__()
        self.input_files = input_files
        self.output_dir = output_dir
        self.processor = PharmaBillProcessor()

    def run(self):
        total = len(self.input_files)
        for i, pdf_path in enumerate(self.input_files):
            try:
                # Update progress
                self.progress.emit(int((i / total) * 100))
                self.message.emit(f"Processing {os.path.basename(pdf_path)}...")
                
                # Process bill
                data, error = self.processor.process_bill(pdf_path)
                if error:
                    self.error.emit(pdf_path, error)
                    continue
                
                # Generate output filename
                filename = os.path.basename(pdf_path)
                output_path = os.path.join(
                    self.output_dir,
                    f"{os.path.splitext(filename)[0]}_extracted.csv"
                )
                
                # Generate CSV
                output_file = self.processor.generate_csv(data, output_path)
                self.result.emit(pdf_path, output_file)
                
                self.message.emit(f"Successfully processed {filename}")
            except Exception as e:
                self.error.emit(pdf_path, str(e))
        
        self.progress.emit(100)
        self.completed.emit()


class PharmaBillExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pharma Bill Extractor")
        self.setGeometry(100, 100, 800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        file_layout.addWidget(self.file_list)
        
        # Buttons
        btn_layout = QVBoxLayout()
        self.add_btn = QPushButton("Add Files")
        self.add_btn.clicked.connect(self.add_files)
        btn_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_files)
        btn_layout.addWidget(self.remove_btn)
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_files)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        file_layout.addLayout(btn_layout)
        layout.addLayout(file_layout)
        
        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Directory:"))
        
        self.output_label = QLabel("Not selected")
        self.output_label.setStyleSheet("border: 1px solid gray; padding: 3px;")
        output_layout.addWidget(self.output_label, 1)
        
        self.output_btn = QPushButton("Browse...")
        self.output_btn.clicked.connect(self.select_output_dir)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)
        
        # Progress
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Log
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)
        
        # Process button
        self.process_btn = QPushButton("Process Bills")
        self.process_btn.clicked.connect(self.process_bills)
        self.process_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;"
        )
        layout.addWidget(self.process_btn)
        
        # Status
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)
        
        # Initialize
        self.output_dir = ""
        self.processing_thread = None
        self.log("Application started. Ready to process bills.")

    def add_files(self):
        """Add PDF files to the processing list"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Pharma Bill PDFs", "", 
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if files:
            for file in files:
                if file not in [self.file_list.item(i).text() for i in range(self.file_list.count())]:
                    self.file_list.addItem(file)
            self.log(f"Added {len(files)} file(s)")

    def remove_files(self):
        """Remove selected files from the list"""
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self.log("Removed selected files")

    def clear_files(self):
        """Clear all files from the list"""
        self.file_list.clear()
        self.log("Cleared all files")

    def select_output_dir(self):
        """Select output directory for CSV files"""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir = directory
            self.output_label.setText(directory)
            self.log(f"Output directory set to: {directory}")

    def log(self, message):
        """Add message to log area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        self.status_label.setText(message)

    def process_bills(self):
        """Start processing the selected bills"""
        # Validation
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "No Files", "Please add at least one PDF file to process.")
            return
        
        if not self.output_dir:
            QMessageBox.warning(self, "No Output Directory", "Please select an output directory.")
            return
        
        if self.processing_thread and self.processing_thread.isRunning():
            self.log("Processing already in progress")
            return
        
        # Get file paths
        input_files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        
        # Disable UI during processing
        self.set_ui_enabled(False)
        
        # Create and start processing thread
        self.processing_thread = ProcessingThread(input_files, self.output_dir)
        self.processing_thread.progress.connect(self.progress_bar.setValue)
        self.processing_thread.message.connect(self.log)
        self.processing_thread.result.connect(self.handle_result)
        self.processing_thread.error.connect(self.handle_error)
        self.processing_thread.completed.connect(self.processing_completed)
        self.processing_thread.start()

    def handle_result(self, input_path, output_path):
        """Handle successful processing result"""
        input_file = os.path.basename(input_path)
        output_file = os.path.basename(output_path)
        self.log(f"Created: {output_file} from {input_file}")

    def handle_error(self, input_path, error):
        """Handle processing error"""
        input_file = os.path.basename(input_path)
        self.log(f"Error processing {input_file}: {error}")

    def processing_completed(self):
        """Handle processing completion"""
        self.log("All files processed!")
        self.set_ui_enabled(True)
        
        # Show completion message
        QMessageBox.information(
            self, 
            "Processing Complete", 
            "All bills have been processed. Check the output directory for CSV files."
        )

    def set_ui_enabled(self, enabled):
        """Enable/disable UI elements during processing"""
        self.add_btn.setEnabled(enabled)
        self.remove_btn.setEnabled(enabled)
        self.clear_btn.setEnabled(enabled)
        self.output_btn.setEnabled(enabled)
        self.process_btn.setEnabled(enabled)
        self.process_btn.setText("Processing..." if not enabled else "Process Bills")

    def closeEvent(self, event):
        """Handle application close"""
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Processing in Progress",
                "Files are still being processed. Are you sure you want to quit?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.processing_thread.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    # Create application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Create and show main window
    window = PharmaBillExtractorApp()
    window.show()
    
    # Run application
    sys.exit(app.exec_())