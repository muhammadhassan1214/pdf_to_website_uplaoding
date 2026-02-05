import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from datetime import datetime

# Add the project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class PDFProcessorApp:
    """GUI Application for PDF to Website Automation"""

    def __init__(self, root):
        self.root = root
        self.root.title("PDF to Website Automation")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)

        # State variables
        self.is_running = False
        self.stop_requested = False
        self.processing_thread = None
        self.driver = None
        self.pdf_path = tk.StringVar()
        self.reference_number = tk.StringVar()

        # Configure style
        self.style = ttk.Style()
        self.style.configure('Start.TButton', font=('Helvetica', 11, 'bold'))
        self.style.configure('Stop.TButton', font=('Helvetica', 11, 'bold'))

        self._setup_ui()
        self._setup_logging()

    def _setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_label = ttk.Label(
            main_frame,
            text="PDF to Website Automation Tool",
            font=('Helvetica', 16, 'bold')
        )
        header_label.pack(pady=(0, 15))

        # PDF Path Selection Frame
        path_frame = ttk.LabelFrame(main_frame, text="PDF File Selection", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 10))

        # Path entry and browse button
        path_container = ttk.Frame(path_frame)
        path_container.pack(fill=tk.X)

        path_label = ttk.Label(path_container, text="PDF Path:")
        path_label.pack(side=tk.LEFT, padx=(0, 10))

        path_entry = ttk.Entry(path_container, textvariable=self.pdf_path, width=60)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        browse_btn = ttk.Button(
            path_container,
            text="Browse...",
            command=self._browse_file
        )
        browse_btn.pack(side=tk.LEFT)

        # Hint label
        hint_label = ttk.Label(
            path_frame,
            text="Select a PDF file or leave empty to process all PDFs from the documents folder",
            font=('Helvetica', 9, 'italic'),
            foreground='gray'
        )
        hint_label.pack(anchor=tk.W, pady=(5, 0))

        # Reference Number Frame
        ref_frame = ttk.LabelFrame(main_frame, text="Reference Number (Optional)", padding="10")
        ref_frame.pack(fill=tk.X, pady=(0, 10))

        # Reference number entry
        ref_container = ttk.Frame(ref_frame)
        ref_container.pack(fill=tk.X)

        ref_label = ttk.Label(ref_container, text="Reference:")
        ref_label.pack(side=tk.LEFT, padx=(0, 10))

        ref_entry = ttk.Entry(ref_container, textvariable=self.reference_number, width=15)
        ref_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Hint label for reference
        ref_hint_label = ttk.Label(
            ref_frame,
            text="Enter a reference number (e.g., A12) to append its text to product descriptions",
            font=('Helvetica', 9, 'italic'),
            foreground='gray'
        )
        ref_hint_label.pack(anchor=tk.W, pady=(5, 0))

        # Control Buttons Frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)

        # Start Button
        self.start_btn = ttk.Button(
            control_frame,
            text="▶ Start Processing",
            command=self._start_processing,
            style='Start.TButton',
            width=20
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Stop Button
        self.stop_btn = ttk.Button(
            control_frame,
            text="■ Stop",
            command=self._stop_processing,
            style='Stop.TButton',
            width=20,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Clear Log Button
        clear_btn = ttk.Button(
            control_frame,
            text="Clear Log",
            command=self._clear_log,
            width=15
        )
        clear_btn.pack(side=tk.RIGHT)

        # Status Label
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(
            status_frame,
            text="Status: Ready",
            font=('Helvetica', 10)
        )
        self.status_label.pack(side=tk.LEFT)

        # Progress Bar
        self.progress = ttk.Progressbar(
            status_frame,
            mode='indeterminate',
            length=200
        )
        self.progress.pack(side=tk.RIGHT)

        # Log Frame
        log_frame = ttk.LabelFrame(main_frame, text="Processing Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        # Log Text Area with Scrollbar
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            state=tk.DISABLED,
            bg='#1e1e1e',
            fg='#d4d4d4'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for colored output
        self.log_text.tag_configure('INFO', foreground='#4ec9b0')
        self.log_text.tag_configure('WARNING', foreground='#dcdcaa')
        self.log_text.tag_configure('ERROR', foreground='#f14c4c')
        self.log_text.tag_configure('SUCCESS', foreground='#6a9955')
        self.log_text.tag_configure('TIMESTAMP', foreground='#808080')

    def _setup_logging(self):
        """Setup logging to redirect to the GUI"""
        # Create a custom log handler that writes to our text widget
        class TextHandler:
            def __init__(self, text_widget, app):
                self.text_widget = text_widget
                self.app = app

            def write(self, message):
                if message.strip():
                    self.app._log_message(message.strip())

            def flush(self):
                pass

        # Redirect stdout to the text widget
        self.text_handler = TextHandler(self.log_text, self)

    def _log_message(self, message, level='INFO'):
        """Add a message to the log"""
        self.log_text.configure(state=tk.NORMAL)

        timestamp = datetime.now().strftime('%H:%M:%S')

        # Determine log level from message
        if 'ERROR' in message or 'Fehler' in message:
            level = 'ERROR'
        elif 'WARNING' in message or 'Warnung' in message:
            level = 'WARNING'
        elif 'SUCCESS' in message or 'erfolgreich' in message.lower() or 'created' in message.lower():
            level = 'SUCCESS'

        self.log_text.insert(tk.END, f"[{timestamp}] ", 'TIMESTAMP')
        self.log_text.insert(tk.END, f"{message}\n", level)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _browse_file(self):
        """Open file dialog to select PDF"""
        file_path = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=os.path.join(PROJECT_ROOT, "documents")
        )
        if file_path:
            self.pdf_path.set(file_path)
            self._log_message(f"Selected file: {file_path}")

    def _clear_log(self):
        """Clear the log text area"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _update_status(self, status_text, is_running=None):
        """Update the status label"""
        self.status_label.config(text=f"Status: {status_text}")
        if is_running is not None:
            self.is_running = is_running

    def _start_processing(self):
        """Start the PDF processing in a separate thread"""
        if self.is_running:
            messagebox.showwarning("Warning", "Processing is already running!")
            return

        # Get the PDF path
        pdf_path = self.pdf_path.get().strip()

        # Validate if a specific file is selected
        if pdf_path and not os.path.exists(pdf_path):
            messagebox.showerror("Error", f"File not found: {pdf_path}")
            return

        # Update UI state
        self.is_running = True
        self.stop_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start(10)
        self._update_status("Processing...")

        self._log_message("=" * 50)
        self._log_message("Starting PDF processing...", 'INFO')
        if pdf_path:
            self._log_message(f"Processing specific file: {pdf_path}")
        else:
            self._log_message("Processing all PDFs from documents folder")

        ref_num = self.reference_number.get().strip()
        if ref_num:
            self._log_message(f"Reference number: {ref_num}")
        self._log_message("=" * 50)

        # Start processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self._run_processing,
            args=(pdf_path, ref_num),
            daemon=True
        )
        self.processing_thread.start()

    def _stop_processing(self):
        """Stop the processing"""
        if not self.is_running:
            return

        self._log_message("Stop requested... Stopping all operations.", 'WARNING')
        self.stop_requested = True
        self._update_status("Stopping...")

        # Close the driver if it exists
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                self._log_message("Browser closed.", 'INFO')
            except Exception as e:
                self._log_message(f"Error closing browser: {e}", 'ERROR')

        # Wait briefly for the thread to acknowledge the stop
        if self.processing_thread and self.processing_thread.is_alive():
            # Give the thread a short time to stop gracefully
            self.processing_thread.join(timeout=2.0)
            if self.processing_thread.is_alive():
                self._log_message("Processing thread terminated.", 'INFO')

        self._processing_complete()
        self._log_message("Processing stopped successfully.", 'SUCCESS')

    def _processing_complete(self):
        """Called when processing is complete or stopped"""
        self.is_running = False
        self.stop_requested = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.stop()
        self._update_status("Ready")

    def _run_processing(self, pdf_path=None, reference_number=None):
        """Run the main processing logic"""
        try:
            # Import here to avoid circular imports - use importlib for dynamic import
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "main_processor",
                os.path.join(os.path.dirname(__file__), "main_processor.py")
            )
            main_processor = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_processor)

            # Pass the GUI instance for logging and stop checking
            result = main_processor.run_automation(
                pdf_path=pdf_path if pdf_path else None,
                reference_number=reference_number if reference_number else None,
                gui_callback=self._log_message,
                stop_checker=lambda: self.stop_requested,
                driver_setter=self._set_driver
            )

            if result:
                self.root.after(0, lambda: self._log_message("Processing completed successfully!", 'SUCCESS'))
            else:
                self.root.after(0, lambda: self._log_message("Processing finished with warnings.", 'WARNING'))

        except Exception as e:
            self.root.after(0, lambda: self._log_message(f"Error during processing: {e}", 'ERROR'))
        finally:
            self.root.after(0, self._processing_complete)

    def _set_driver(self, driver):
        """Set the driver reference for cleanup"""
        self.driver = driver

    def on_closing(self):
        """Handle window close event"""
        if self.is_running:
            if messagebox.askokcancel("Quit", "Processing is still running. Do you want to stop and quit?"):
                self._stop_processing()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """Main entry point for the GUI application"""
    root = tk.Tk()
    app = PDFProcessorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

