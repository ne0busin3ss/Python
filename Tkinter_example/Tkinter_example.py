import tkinter as tk

def say_hi():
    """Prints a greeting message."""
    print("Hello Dave, outstanding work!")

class Application(tk.Frame):
    """A simple Tkinter application with two buttons."""
    def __init__(self, master=None):
        """Initialize the application frame and widgets."""
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

    def create_widgets(self):
        """Create and configure the widgets for the application."""
        self.hello_button = tk.Button(
            self,
            text="Hello\n(click me)",
            command=say_hi
        )
        self.hello_button.pack(side="left")

        self.quit_button = tk.Button(
            self,
            text="QUIT",
            fg="red",
            command=self.master.destroy
        )
        self.quit_button.pack(side="left")

def main():
    """Create the main window and run the application."""
    root = tk.Tk()
    root.title("Tkinter Example")
    app = Application(master=root)
    app.mainloop()

if __name__ == "__main__":
    main()