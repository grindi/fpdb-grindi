class FpdbError(Exception):
    def __init__(self, value=""):
        self.value = value
    def __str__(self):
        return repr(self.value)

class FpdbParseError(FpdbError): 
    def __init__(self,value='',hid='', hand=None):
        self.value = value
        self.hid = hid
        self.hand = hand
    def __str__(self):
        if self.hid:
            return repr("HID:"+self.hid+", "+self.value)
        else:
            return repr(self.value)

class FpdbDatabaseError(FpdbError):
    pass

class FpdbMySQLFailedError(FpdbDatabaseError):
    pass

class DuplicateError(FpdbError):
    pass

class IncompleteHandError(FpdbParseError):
    pass

