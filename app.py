import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox
from gui import main as start_server, active_process

class NativeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Apple Silicon Video Upscaler")
        self.root.geometry("450x250")
        self.root.resizable(False, False)
        
        # Dark Theme Styling
        self.root.configure(bg="#0b0f19")
        
        # Title Label
        title_label = tk.Label(
            root,
            text="Apple Silicon Video Upscaler",
            font=("Outfit", 18, "bold"),
            fg="#f3f4f6",
            bg="#0b0f19"
        )
        title_label.pack(pady=20)
        
        # Description Label
        desc_label = tk.Label(
            root,
            text="Le serveur d'upscaling IA est actif.",
            font=("Outfit", 12),
            fg="#9ca3af",
            bg="#0b0f19"
        )
        desc_label.pack(pady=5)
        
        # Link Label
        link_label = tk.Label(
            root,
            text="http://127.0.0.1:8080",
            font=("Outfit", 12, "underline"),
            fg="#6366f1",
            bg="#0b0f19",
            cursor="hand2"
        )
        link_label.pack(pady=5)
        link_label.bind("<Button-1>", lambda e: self.open_browser())
        
        # Frame for buttons
        btn_frame = tk.Frame(root, bg="#0b0f19")
        btn_frame.pack(pady=20)
        
        # Open Browser Button
        open_btn = tk.Button(
            btn_frame,
            text="Ouvrir le navigateur",
            font=("Outfit", 10, "bold"),
            fg="#0b0f19",
            bg="#6366f1",
            activebackground="#4f46e5",
            command=self.open_browser,
            width=18,
            height=2
        )
        open_btn.pack(side=tk.LEFT, padx=10)
        
        # Exit Button
        exit_btn = tk.Button(
            btn_frame,
            text="Quitter & Arrêter",
            font=("Outfit", 10, "bold"),
            fg="#ffffff",
            bg="#ef4444",
            activebackground="#dc2626",
            command=self.on_closing,
            width=18,
            height=2
        )
        exit_btn.pack(side=tk.LEFT, padx=10)
        
        # Handle Close Window Action
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start GUI Server Thread
        self.server_thread = threading.Thread(target=start_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Auto-open browser on startup
        # We wait 1 second to let the server bind to the port
        self.root.after(1000, self.open_browser)

    def open_browser(self):
        webbrowser.open("http://127.0.0.1:8080")

    def on_closing(self):
        # Kill any active upscale processes before exiting
        global active_process
        if active_process:
            try:
                active_process.terminate()
            except Exception:
                pass
        self.root.destroy()
        sys.exit(0)

def main():
    root = tk.Tk()
    app = NativeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
