"""Module for signalling upon stimuli appearance using the serial or 
parallel ports."""

SERPORT = None
PARPORT = None

STATE = None
OLD_STATE = None

# Arranged in order of decreasing priority
USER_START = 128 # 0b10000000
FIX_START = 99   # 0b01100011
TRACK_START = 98 # 0b01100010
TRACK_STOP = 89  # 0b01011001
FIX_STOP = 88    # 0b01011000
GROUP_START = 60 # 0b00111100
GROUP_STOP = 40  # 0b00101000
BOARD_FLIP = 10  # 0b00001010

FLIP_SIG_PER = 10

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

def set_state(NEW_STATE):
    global STATE
    global OLD_STATE
    if NEW_STATE == None or NEW_STATE >= STATE:
        OLD_STATE = STATE
        STATE = NEW_STATE

def set_board_flip(board_id):
    set_state(BOARD_FLIP + board_id)

def set_group_start(group_id):
    set_state(GROUP_START + group_id)

def set_group_stop(group_id):
    set_state(GROUP_STOP + group_id)

def set_user_start():
    set_state(USER_START)

def set_fix_start():
    set_state(FIX_START)

def set_fix_stop():
    set_state(FIX_STOP)

def set_track_start():
    set_state(TRACK_START)

def set_track_stop():
    set_state(TRACK_STOP)

def set_null():
    set_state(None)

def send(sigser, sigpar):
    if sigser:
        ser_send()
    if STATE != OLD_STATE:
        if sigpar:
            par_send()

def quit(sigser, sigpar):
    set_null()
    if sigser:
        ser_quit()
    if sigpar:
        par_quit()
    
