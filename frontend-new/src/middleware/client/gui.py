from tkinter import *
from tkinter import messagebox

#region --- Utils ---
class GUIQuit(Exception):
    """Gross and hacky way to communicate GUI closure to parent process."""
    pass

class Alert:
    def __init__(self, title, message, callback=None):
        self.title = title
        self.message = message
        self.callback = callback

    def show(self):
        return messagebox.showwarning(self.title, self.message, command=self.callback)

class Question:
    def __init__(self, title, question, callback=None):
        self.title = title
        self.question = question
        self.callback = callback

    def show(self):
        return messagebox.askquestion(self.title, self.question)
#endregion


#region --- GUI Interface ---
from threading import Thread
from typing import Callable, Any
from abc import ABC, abstractmethod
class GUIInterface(ABC): # TODO: Potentially subclass Thread if necessary to avoid blocking

    def __init__(self):
        self.root = Tk()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.quit_message = None
        self.quit_flag = False
        self.ready_flag = False

        self.root.update_idletasks() # Resolves bug in which Tk can only take focus after alt-tabbing if an Alert is displayed.

    def set_ready_flag(self, state: bool):
        self.ready_flag = state
    
    def is_ready(self):
        return self.ready_flag
    
    def has_quit(self):
        return self.quit_flag
    
    def alert(self, title, message, callback=None):
        return Alert(title, message, callback).show()

    def question(self, title, message, callback=None):
        return Question(title, message, callback).show()

    #region --- Form Creation Helpers ---
    class Form:
        def __init__(self, entries, *fields):
            self.entries = entries
            self.fields = fields

        def getEntries(self):
            """Return values of entries in order received in `self.fields`"""
            values = [None]*len(self.fields)
            for i, field in enumerate(self.fields):
                values[i] = self.entries[field[0]].get()
            return values

        def setDefaultValues(self):
            """Return all text boxes in `self.entries` to default values specified in `self.fields`"""
            for field in self.fields:
                text_box = self.entries[field[0]]
                text_box.delete(0,END)
                text_box.insert(0,field[1])


    def createForm(self, on_submit: Callable[..., Any], button_text: str = 'Submit', *fields):
        """Pack a form, consisting of rows of labels and fields and a submit button at the bottom, into the root window.
        
        Parameters
        ----------
        on_submit : func
            Function that runs when submit button is pressed. Will be passed field entries at time of submission in order received in `fields`
        field : tuple
            Specifications for a field; displayed in order received.
            field[0] : str
                Label of field
            field[1] : str
                Default value of field
        """
        entries = {}
        for field in fields:
            row = Frame(self.root)
            label = Label(row, text=field[0], anchor="w")
            text_box = Entry(row)
            
            row.pack(side = TOP, fill = X, padx = 5, pady = 5)
            label.pack(side=LEFT)
            text_box.pack(side = RIGHT, expand = YES, fill = X)

            entries[field[0]] = text_box

        form = self.Form(entries, *fields)
        form.setDefaultValues()

        on_submit_ = lambda: on_submit(*form.getEntries())
        button = Button(self.root, text=button_text, command=on_submit_)
        button.pack(side = BOTTOM, padx = 5, pady = 5)
        self.root.bind('<Return>', (lambda e : on_submit_())) # Submits form when enter/return is pressed

        return form
    #endregion

    def run(self):
        self.ready_flag = False
        self.on_run()
        self.root.mainloop() # Blocking
        if self.quit_flag:
            self.quit_flag = False
            if self.quit_message:
                raise GUIQuit(self.quit_message)
            raise GUIQuit(f"{self.__class__.__name__} closed by user.")
        self.ready_flag = True

    def quit(self, msg=None):
        self.on_quit()
        self.quit_flag = True
        self.quit_message = msg
        self.root.destroy()

    @abstractmethod
    def on_run(self):
        """Perform any additional functions necessary on run."""
        pass

    @abstractmethod
    def on_quit(self):
        """Perform any additional cleanup on quit."""
        pass
#endregion


#region --- InitClientGUI ---
class InitClientGUI(GUIInterface):
    """GUI to initialize Client (set Server endpoint for connection)."""
    DEFAULT_IP = '127.0.0.1'
    DEFAULT_PORT = '5000'

    def __init__(self):
        super().__init__()
        self.root.title("Quantum Video Chat")

        self.server_endpoint = None
        self.form = self.createForm(self.connectButton, 'Connect', ('Server IP:', self.DEFAULT_IP), ('Port:', self.DEFAULT_PORT))

    # TODO: This function may be better defined in main_client.py
    #       or maybe not; just surface level validation is ok since Client
    #       can do its own validation upon connect.
    def verifyServerIP(self, ip, port):
        return port.isdigit()

    def connectButton(self, ip, port):
        if self.verifyServerIP(ip,port):
            self.server_endpoint = ip, int(port)
            self.root.destroy()
        else:
            alert = Alert('Warning', 'Please enter a valid IP and Port.')
            alert.show()
            self.form.setDefaultValues()
            self.server_endpoint = None

    def on_quit(self):
        pass

    def on_run(self):
        pass
#endregion


#region --- Main GUI ---
class MainGUI(GUIInterface):
    """
    GUI to interface with server from. Currently only allows user to request to connect to a peer with specified user ID.
    """
    DEFAULT_ID = '12345'

    def __init__(self, user_id):
        super().__init__()
        self.root.title(f"Quantum Video Chat - {user_id}")

        self.peer_id = None
        self.form = self.createForm(self.connectButton, 'Connect', ('User ID:', '12345'))

    def verifyID(self, user_id):
        return len(user_id) == 5

    def connectButton(self, user_id):
        if self.verifyID(user_id):
            self.peer_id = user_id
            self.root.destroy()
        else:
            alert = Alert('Warning', 'Please enter a valid user ID (5-digit alphanumeric).')
            alert.show()
            self.form.setDefaultValues()
            self.peer_id = None

    def on_quit(self):
        pass

    def on_run(self):
        pass
#endregion

class ChatGUI:
    pass