### Step 1: Set Up Your Environment

Make sure you have Python installed on your machine. You can also install the required libraries using pip:

```bash
pip install pandas tkinter
```

### Step 2: Create the CSV File

Ensure you have a `Referentiedata.csv` file with appropriate headers. For example:

```csv
Name,Email,Phone,Role
```

### Step 3: Create the Application

Here’s a simple Python script that creates a GUI for adding entries to the CSV file:

```python
import pandas as pd
import tkinter as tk
from tkinter import messagebox

# Function to add entry to CSV
def add_entry():
    name = entry_name.get()
    email = entry_email.get()
    phone = entry_phone.get()
    role = entry_role.get()

    # Validation
    if not name or not email or not phone or not role:
        messagebox.showerror("Input Error", "All fields are required.")
        return

    if not validate_email(email):
        messagebox.showerror("Input Error", "Invalid email format.")
        return

    if not validate_phone(phone):
        messagebox.showerror("Input Error", "Invalid phone number format.")
        return

    # Append to CSV
    new_entry = pd.DataFrame([[name, email, phone, role]], columns=['Name', 'Email', 'Phone', 'Role'])
    new_entry.to_csv('Referentiedata.csv', mode='a', header=False, index=False)

    messagebox.showinfo("Success", "Entry added successfully!")
    clear_fields()

def validate_email(email):
    import re
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def validate_phone(phone):
    return phone.isdigit() and len(phone) in [10, 11]  # Adjust based on your phone number format

def clear_fields():
    entry_name.delete(0, tk.END)
    entry_email.delete(0, tk.END)
    entry_phone.delete(0, tk.END)
    entry_role.delete(0, tk.END)

# Create the main window
root = tk.Tk()
root.title("Add Entry to Referentiedata")

# Create input fields
tk.Label(root, text="Name").grid(row=0, column=0)
entry_name = tk.Entry(root)
entry_name.grid(row=0, column=1)

tk.Label(root, text="Email").grid(row=1, column=0)
entry_email = tk.Entry(root)
entry_email.grid(row=1, column=1)

tk.Label(root, text="Phone").grid(row=2, column=0)
entry_phone = tk.Entry(root)
entry_phone.grid(row=2, column=1)

tk.Label(root, text="Role").grid(row=3, column=0)
entry_role = tk.Entry(root)
entry_role.grid(row=3, column=1)

# Create Add Entry button
btn_add = tk.Button(root, text="Add Entry", command=add_entry)
btn_add.grid(row=4, columnspan=2)

# Run the application
root.mainloop()
```

### Step 4: Share the Application

1. **Distributing the Script**: Share the Python script with your team members. They will need Python installed on their machines to run it.

2. **CSV File Location**: Ensure that the `Referentiedata.csv` file is in the same directory as the script or modify the script to point to the correct path.

3. **Collaboration**: If multiple users will be adding entries simultaneously, consider using a database (like SQLite or PostgreSQL) instead of a CSV file to avoid conflicts.

### Step 5: Additional Features

- **Error Logging**: Implement logging to track errors or issues.
- **User Authentication**: Add user authentication if sensitive data is being handled.
- **Data Backup**: Create a backup mechanism for the CSV file before writing new entries.

This simple application provides a user-friendly interface for adding entries to a CSV file with basic validation. You can expand upon this foundation based on your team's specific needs.