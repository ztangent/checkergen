"""Module for sending triggers upon various events through the serial or 
parallel ports."""

SERPORT = None
PARPORT = None

available = {'serial': False, 'parallel': False}

try:
    import serial

    try:
        test_port = serial.Serial(0)
        test_port.close()
        del test_port
        available['serial'] = True
    except serial.serialutil.SerialException:
        pass
except ImportError:
    pass

try:
    import parallel
    try:
        test_port = parallel.Parallel()
        del test_port
        available['parallel'] = True
    except:
        pass
except ImportError:
    pass

if available['serial']:
    def ser_init():
        global SERPORT
        SERPORT = serial.Serial(0)

    def ser_send(code):
        global SERPORT
        SERPORT.write(code)

    def ser_quit():
        global SERPORT
        SERPORT.close()
        SERPORT = None

if available['parallel']:
    def par_init():
        global PARPORT
        PARPORT = parallel.Parallel()
        PARPORT.setData(0)

    def par_send(code):
        global PARPORT
        PARPORT.setData(code)

    def par_quit():
        global PARPORT
        PARPORT.setData(0)
        PARPORT = None

def init(trigser, trigpar):
    if trigser:
        ser_init()
    if trigpar:
        par_init()

def send(trigser, trigpar, code):
    if trigser:
        ser_send(code)
    if trigpar:
        par_send(code)

def quit(trigser, trigpar):
    send(trigser, trigpar, 0)
    if trigser:
        ser_quit()
    if trigpar:
        par_quit()
