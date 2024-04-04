import tkinter as tk

# Create a window
window = tk.Tk()

# Create a button
button = tk.Button(text="Click me!")

# Add the button to the window
button.pack()

# Bind the button to a function
def on_click():
  print("You clicked the button!")

button.config(command=on_click)

# Show the window
window.mainloop()