"""Module for sending triggers upon various events through the serial or 
parallel ports."""

NULL_STATE = {'block': 0, 'tracking': 0, 'fixation': 0,
              'group': 0, 'shape': 0, 'gid': 0, 'sid': 0,
              'event': 0}
CUR_STATE = dict(NULL_STATE)
PREV_STATE = dict(NULL_STATE)

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

    def ser_send(statebyte):
        global SERPORT
        SERPORT.write(statebyte)

    def ser_quit():
        global SERPORT
        SERPORT.close()
        SERPORT = None

if available['parallel']:
    def par_init():
        global PARPORT
        PARPORT = parallel.Parallel()
        PARPORT.setData(0)

    def par_send(statebyte):
        global PARPORT
        PARPORT.setData(statebyte)

    def par_quit():
        global PARPORT
        PARPORT.setData(0)
        PARPORT = None

def init(trigser, trigpar):
    global CUR_STATE
    global PREV_STATE
    CUR_STATE = NULL_STATE
    PREV_STATE = NULL_STATE
    if trigser:
        ser_init()
    if trigpar:
        par_init()

def set_state(fieldname, value):
    global CUR_STATE
    global PREV_STATE
    PREV_STATE = CUR_STATE
    CUR_STATE[fieldname] = value
    CUR_STATE['event'] = 1
    
def set_null():
    set_state(NULL_STATE)

def send(trigser, trigpar):
    statebyte = ''.join([str(CUR_STATE[name]) for 
                         name in ['block', 'tracking', 'fixation',
                                  'group', 'shape']]).ljust(8,'0')
    statebyte = int(statebyte, 2)
    # Preferentially send group id over shape id
    if CUR_STATE['group'] != PREV_STATE['group']:
        statebyte += CUR_STATE['gid'] + 1
    elif CUR_STATE['shape'] > PREV_STATE['shape']:
        statebyte += CUR_STATE['sid']
    if CUR_STATE != PREV_STATE:
        if trigser:
            ser_send(statebyte)
        if trigpar:
            par_send(statebyte)

def quit(trigser, trigpar):
    set_null()
    if trigser:
        ser_quit()
    if trigpar:
        par_quit()
