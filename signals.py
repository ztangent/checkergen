"""Module for signalling upon stimuli appearance using the serial or 
parallel ports."""

SERPORT = None
SERSTATE = 0
SERFLIP = False
PARPORT = None
PARSTATE = 0
PARFLIP = False
GROUP_ON = 42 # 0b00101010
GROUP_OFF = 17 # 0b00000000

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

    def ser_set_on():
        global SERSTATE
        if SERSTATE != GROUP_ON:
            SERFLIP = True
            SERSTATE = GROUP_ON
        
    def ser_set_off():
        global SERSTATE
        if SERSTATE != GROUP_OFF:
            SERFLIP = True
            SERSTATE = GROUP_OFF

    def ser_send():
        global SERPORT
        if SERFLIP:
            SERPORT.write(str(SERSTATE))
            SERFLIP = False

    def ser_quit():
        global SERPORT
        SERPORT.close()
        SERPORT = None
else:
    msg = 'serial port functionality not available'
    def ser_init(msg=msg):
        raise NotImplementedError(msg)

    def ser_set_on(msg=msg):
        raise NotImplementedError(msg)

    def ser_set_off(msg=msg):
        raise NotImplementedError(msg)

    def ser_send(msg=msg):
        raise NotImplementedError(msg)

    def ser_quit(msg=msg):
        raise NotImplementedError(msg)

if available['parallel']:
    def par_init():
        global PARPORT
        PARPORT = parallel.Parallel()

    def par_set_on():
        global PARSTATE
        if PARSTATE != GROUP_ON:
            PARFLIP = True
            PARSTATE = GROUP_ON
        
    def par_set_off():
        global PARSTATE
        if PARSTATE != GROUP_OFF:
            PARFLIP = True
            PARSTATE = GROUP_OFF

    def par_send():
        global PARPORT
        if PARFLIP:
            PARPORT.setData(PARSTATE)
            PARFLIP = False

    def par_quit():
        global PARPORT
        PARPORT = None
else:
    msg = 'parallel port functionality not available'
    def par_init(msg=msg):
        raise NotImplementedError(msg)

    def par_set_on():
        raise NotImplementedError(msg)

    def par_set_off():
        raise NotImplementedError(msg)

    def par_send():
        raise NotImplementedError(msg)

    def par_quit(msg=msg):
        raise NotImplementedError(msg)
