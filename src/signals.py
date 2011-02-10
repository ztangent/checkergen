"""Module for signalling upon stimuli appearance using the serial or 
parallel ports."""

SERPORT = None
PARPORT = None
STATE = None
OLD_STATE = None
BOARD_FLAG = 64 # 0b01000000
GROUP_START = 42 # 0b00101010
GROUP_STOP = 17 # 0b00010001

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

    def ser_send():
        global SERPORT
        global STATE
        if STATE != None:
            SERPORT.write(str(STATE))

    def ser_quit():
        global SERPORT
        SERPORT.close()
        SERPORT = None

if available['parallel']:
    def par_init():
        global PARPORT
        PARPORT = parallel.Parallel()
        PARPORT.setData(0)

    def par_send():
        global PARPORT
        global STATE
        if STATE != None:
            PARPORT.setData(STATE)
        else:
            PARPORT.setData(0)

    def par_quit():
        global PARPORT
        PARPORT.setData(0)
        PARPORT = None

def init(sigser, sigpar):
    global STATE
    global OLD_STATE
    STATE = None
    OLD_STATE = None
    if sigser:
        ser_init()
    if sigpar:
        par_init()

def set_board_flip(board_id):
    global STATE
    global OLD_STATE
    OLD_STATE = STATE
    STATE = BOARD_FLAG + board_id

def set_group_start():
    global STATE
    global OLD_STATE
    OLD_STATE = STATE
    STATE = GROUP_START

def set_group_stop():
    global STATE
    global OLD_STATE
    OLD_STATE = STATE
    STATE = GROUP_STOP

def set_null():
    global STATE
    global OLD_STATE
    OLD_STATE = STATE
    STATE = None

def send(sigser, sigpar):
    if sigser:
        ser_send()
    if STATE != OLD_STATE:
        if sigpar:
            par_send()

def quit(sigser, sigpar):
    global STATE
    STATE = None
    if sigser:
        ser_quit()
    if sigpar:
        par_quit()
    