#!/usr/bin/env python3
"""
History Browser for BIRP v2
Browse and analyze recorded transactions
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

class HistoryBrowser(tk.Toplevel):
    """Transaction History Browser Window"""
    
    def __init__(self, parent, history):
        super().__init__(parent)
        
        self.title("BIRP v2 - Transaction History")
        self.geometry("1000x700")
        self.transient(parent)
        
        self.history = history
        self.current_index = 0
        
        self.setup_ui()
        self.load_transactions()
        
    def setup_ui(self):
        """Create the UI layout"""
        
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="First", command=self.first_transaction).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Previous", command=self.prev_transaction).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Next", command=self.next_transaction).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Last", command=self.last_transaction).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Label(toolbar, text="Transaction:").pack(side=tk.LEFT, padx=5)
        self.trans_var = tk.StringVar(value="0")
        trans_entry = ttk.Entry(toolbar, textvariable=self.trans_var, width=10)
        trans_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Go", command=self.goto_transaction).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(toolbar, text="Search", command=self.show_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export", command=self.export_transaction).pack(side=tk.LEFT, padx=2)
        
        # Status
        self.status_var = tk.StringVar()
        self.status_var.set("No transactions")
        status_label = ttk.Label(toolbar, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT, padx=10)
        
        # Main content
        content = ttk.PanedWindow(self, orient=tk.VERTICAL)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Transaction list
        list_frame = ttk.LabelFrame(content, text="Transaction List")
        content.add(list_frame, weight=1)
        
        # Create treeview
        columns = ('ID', 'Timestamp', 'Key', 'Host', 'Request', 'Response')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'ID':
                self.tree.column(col, width=50)
            elif col == 'Timestamp':
                self.tree.column(col, width=150)
            elif col == 'Key':
                self.tree.column(col, width=80)
            elif col == 'Host':
                self.tree.column(col, width=150)
            else:
                self.tree.column(col, width=200)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind('<<TreeviewSelect>>', self.on_select_transaction)
        
        # Transaction details
        detail_frame = ttk.LabelFrame(content, text="Transaction Details")
        content.add(detail_frame, weight=2)
        
        # Notebook for request/response
        notebook = ttk.Notebook(detail_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Request tab
        request_frame = ttk.Frame(notebook)
        notebook.add(request_frame, text="Request")
        
        self.request_text = scrolledtext.ScrolledText(
            request_frame,
            wrap=tk.NONE,
            font=('Courier', 10)
        )
        self.request_text.pack(fill=tk.BOTH, expand=True)
        
        # Response tab
        response_frame = ttk.Frame(notebook)
        notebook.add(response_frame, text="Response")
        
        self.response_text = scrolledtext.ScrolledText(
            response_frame,
            wrap=tk.NONE,
            font=('Courier', 10)
        )
        self.response_text.pack(fill=tk.BOTH, expand=True)
        
        # Data tab
        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="Modified Fields")
        
        self.data_text = scrolledtext.ScrolledText(
            data_frame,
            wrap=tk.WORD,
            font=('Courier', 10)
        )
        self.data_text.pack(fill=tk.BOTH, expand=True)
        
        # Fields tab
        fields_frame = ttk.Frame(notebook)
        notebook.add(fields_frame, text="All Fields")
        
        self.fields_text = scrolledtext.ScrolledText(
            fields_frame,
            wrap=tk.WORD,
            font=('Courier', 10)
        )
        self.fields_text.pack(fill=tk.BOTH, expand=True)
        
    def load_transactions(self):
        """Load transactions into the tree view"""
        self.tree.delete(*self.tree.get_children())
        
        if not self.history or len(self.history) == 0:
            self.status_var.set("No transactions")
            return
        
        for idx, trans in enumerate(self.history):
            request_preview = trans.request.stringbuffer[0][:50] if trans.request.stringbuffer else ""
            response_preview = trans.response.stringbuffer[0][:50] if trans.response.stringbuffer else ""
            
            self.tree.insert('', tk.END, values=(
                idx,
                trans.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                trans.key,
                trans.host,
                request_preview,
                response_preview
            ))
        
        self.status_var.set(f"Total transactions: {len(self.history)}")
        
        # Select first transaction
        if len(self.history) > 0:
            first_item = self.tree.get_children()[0]
            self.tree.selection_set(first_item)
            self.tree.focus(first_item)
            self.display_transaction(0)
    
    def on_select_transaction(self, event):
        """Handle transaction selection"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            trans_id = int(item['values'][0])
            self.display_transaction(trans_id)
    
    def display_transaction(self, index):
        """Display transaction details"""
        if index < 0 or index >= len(self.history):
            return
        
        self.current_index = index
        self.trans_var.set(str(index))
        trans = self.history[index]
        
        # Display request
        self.request_text.delete('1.0', tk.END)
        self.request_text.insert('1.0', str(trans.request))
        
        # Display response
        self.response_text.delete('1.0', tk.END)
        self.response_text.insert('1.0', str(trans.response))
        
        # Display modified fields
        self.data_text.delete('1.0', tk.END)
        if trans.data:
            for field in trans.data:
                content = field.contents.strip()
                if content:
                    self.data_text.insert(tk.END, 
                        f"Row: {field.row}, Col: {field.col}\n"
                        f"Content: {content}\n"
                        f"Protected: {field.protected}, Hidden: {field.hidden}\n\n"
                    )
        else:
            self.data_text.insert('1.0', "No modified fields")
        
        # Display all fields
        self.fields_text.delete('1.0', tk.END)
        self.fields_text.insert(tk.END, "=== Request Fields ===\n\n")
        for field in trans.request.fields:
            content = field.contents.strip()
            if content:
                self.fields_text.insert(tk.END,
                    f"[{field.row},{field.col}] {content}\n"
                    f"  Protected: {field.protected}, Hidden: {field.hidden}, "
                    f"Modified: {field.modify}\n\n"
                )
        
        self.fields_text.insert(tk.END, "\n=== Response Fields ===\n\n")
        for field in trans.response.fields:
            content = field.contents.strip()
            if content:
                self.fields_text.insert(tk.END,
                    f"[{field.row},{field.col}] {content}\n"
                    f"  Protected: {field.protected}, Hidden: {field.hidden}, "
                    f"Modified: {field.modify}\n\n"
                )
    
    def first_transaction(self):
        """Go to first transaction"""
        if len(self.history) > 0:
            self.select_transaction(0)
    
    def prev_transaction(self):
        """Go to previous transaction"""
        if self.current_index > 0:
            self.select_transaction(self.current_index - 1)
    
    def next_transaction(self):
        """Go to next transaction"""
        if self.current_index < len(self.history) - 1:
            self.select_transaction(self.current_index + 1)
    
    def last_transaction(self):
        """Go to last transaction"""
        if len(self.history) > 0:
            self.select_transaction(len(self.history) - 1)
    
    def goto_transaction(self):
        """Go to specific transaction"""
        try:
            index = int(self.trans_var.get())
            if 0 <= index < len(self.history):
                self.select_transaction(index)
            else:
                messagebox.showwarning("Invalid Index", 
                    f"Transaction index must be between 0 and {len(self.history)-1}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number")
    
    def select_transaction(self, index):
        """Select transaction in tree view"""
        children = self.tree.get_children()
        if 0 <= index < len(children):
            item = children[index]
            self.tree.selection_set(item)
            self.tree.focus(item)
            self.tree.see(item)
            self.display_transaction(index)
    
    def show_search(self):
        """Show search dialog"""
        dialog = tk.Toplevel(self)
        dialog.title("Search Transactions")
        dialog.geometry("400x200")
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Search for:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        search_entry = ttk.Entry(dialog, width=30)
        search_entry.grid(row=0, column=1, padx=10, pady=10)
        
        search_type = tk.StringVar(value="case_sensitive")
        ttk.Radiobutton(dialog, text="Case-sensitive", variable=search_type, 
                       value="case_sensitive").grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10)
        ttk.Radiobutton(dialog, text="Case-insensitive", variable=search_type, 
                       value="case_insensitive").grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10)
        ttk.Radiobutton(dialog, text="Regex", variable=search_type, 
                       value="regex").grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10)
        
        def do_search():
            term = search_entry.get()
            if not term:
                return
            
            from ..utils.search import find_all
            
            case_sensitive = search_type.get() == "case_sensitive"
            use_regex = search_type.get() == "regex"
            
            results = find_all(self.history, term, case_sensitive, use_regex)
            
            dialog.destroy()
            
            if results:
                self.show_search_results(term, results)
            else:
                messagebox.showinfo("Search Results", f"No matches found for '{term}'")
        
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Search", command=do_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        search_entry.focus()
        dialog.bind('<Return>', lambda e: do_search())
    
    def show_search_results(self, term, results):
        """Show search results"""
        result_window = tk.Toplevel(self)
        result_window.title(f"Search Results for '{term}'")
        result_window.geometry("600x400")
        result_window.transient(self)
        
        ttk.Label(result_window, text=f"Found {len(results)} match(es)").pack(padx=10, pady=10)
        
        # Results list
        columns = ('Transaction', 'Type', 'Row', 'Col')
        tree = ttk.Treeview(result_window, columns=columns, show='headings')
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(result_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        for trans_id, rr, row, col in results:
            trans_type = "Request" if rr == 0 else "Response"
            tree.insert('', tk.END, values=(trans_id, trans_type, row, col))
        
        def on_result_select(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                trans_id = int(item['values'][0])
                self.select_transaction(trans_id)
                result_window.destroy()
        
        tree.bind('<Double-Button-1>', on_result_select)
    
    def export_transaction(self):
        """Export current transaction"""
        if self.current_index < 0 or self.current_index >= len(self.history):
            messagebox.showwarning("No Transaction", "No transaction selected")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                trans = self.history[self.current_index]
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Transaction {self.current_index}\n")
                    f.write(f"Timestamp: {trans.timestamp}\n")
                    f.write(f"Key: {trans.key}\n")
                    f.write(f"Host: {trans.host}\n\n")
                    f.write("=== REQUEST ===\n")
                    f.write(str(trans.request))
                    f.write("\n\n=== RESPONSE ===\n")
                    f.write(str(trans.response))
                
                messagebox.showinfo("Success", f"Transaction exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
