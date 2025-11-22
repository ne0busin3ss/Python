import tkinter as tk
from tkinter import ttk
from typing import Optional

class Application(ttk.Frame):
    """A simple Tkinter application with two buttons."""

    def __init__(self, master: Optional[tk.Tk] = None) -> None:
        """Initialize the application frame and widgets."""
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

    def say_hi(self) -> None:
        """Prints a greeting message."""
        print("Hello Dave, outstanding work!")

    def create_widgets(self) -> None:
        """Create and configure the widgets for the application."""
        self.hello_button = ttk.Button(
            self,
            text="Hello\n(click me)",
            command=self.say_hi
        )
        self.hello_button.pack(side="left")

        # Create a style for the quit button to have red text
        style = ttk.Style()
        style.configure("Quit.TButton", foreground="red")

        self.quit_button = ttk.Button(
            self,
            text="QUIT",
            command=self.master.destroy,
            style="Quit.TButton"
        )
        self.quit_button.pack(side="left")

def main() -> None:
    """Create the main window and run the application."""
    root = tk.Tk()
    root.title("Tkinter Example")
    app = Application(master=root)
    app.mainloop()

if __name__ == "__main__":
    main()