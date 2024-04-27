from tkinter import *

def say_hi():
    print("Hello Super Duper Dave!")


class Application(Frame):

    def createWidgets(self):
        self.QUIT["text"] = "QUIT\n"
        self.QUIT["fg"] = "red"
        self.QUIT["command"] = self.quit

        self.QUIT.pack({"side": "left"})
  
        self.hi_there["text"] = "Hello\n(click me)"
        self.hi_there["command"] = say_hi

        self.hi_there.pack({"side": "left"})

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.hi_there = Button(self)
        self.QUIT = Button(self)
        self.pack()
        self.createWidgets()


root = Tk()
app = Application(master=root)
app.mainloop()
# root.destroy()
 