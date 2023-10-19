from tkinter import *

class InitClientGUI:

    def __init__(self,out):
        self.root = Tk()
        self.root.title("Quantum Video Chat")
        self.default_ip = '127.0.0.1'
        self.default_port = '65431'
        self.out = out
        self.entries = {}
        self.createForm()

    def setDefaultValues(self):
        self.entries["IP"].delete(0,END)
        self.entries["Port"].delete(0,END)
        self.entries["IP"].insert(0,self.default_ip)
        self.entries["Port"].insert(0,self.default_port)
        
    def createForm(self):
        row1 = Frame(self.root)
        IP_label = Label(row1, text = "Server IP", anchor="w")
        IP_field = Entry(row1)
        row1.pack(side = TOP, fill = X, padx = 5, pady = 5)
        IP_label.pack(side = LEFT)
        IP_field.pack(side = RIGHT, expand = YES, fill = X)

        row2 = Frame(self.root)
        Port_label = Label(row2, text = "Port", anchor="w")
        Port_field = Entry(row2)
        row2.pack(side = TOP, fill = X, padx = 5, pady = 5)
        Port_label.pack(side = LEFT)
        Port_field.pack(side = RIGHT, expand = YES, fill = X)

        self.entries["IP"] = IP_field
        self.entries["Port"] = Port_field

        # Default Fields Values:
        self.setDefaultValues()

        b1 = Button(self.root, text = 'Connect',
            command=self.connectButton)
        b1.pack(side = BOTTOM, padx = 5, pady = 5)

        self.root.bind('<Return>', (lambda e : self.connectButton()))

    # TODO:
    # This function may be better defined in main_client.py
    def verifyServerIP(self, HOST, PORT):
        return PORT.isdigit()

    def connectButton(self):
        HOST = self.entries['IP'].get()
        PORT = self.entries['Port'].get()

        if self.verifyServerIP(HOST,PORT):
            self.out[0] = HOST
            self.out[1] = int(PORT)
            self.root.destroy()
            return

        self.reset()

    def reset(self):
        self.setDefaultValues()

        self.out[0] = None
        self.out[1] = None

    def quit(self):
        self.root.quit()

    def run(self):
        self.root.mainloop()