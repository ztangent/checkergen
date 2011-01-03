"""Module for signalling upon stimuli appearance using the serial or 
parallel ports."""

SERPORT = None
PARPORT = None
STIMULI_ON = 42 # 0b00101010
STIMULI_OFF = 0 # 0b00000000

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

    def ser_send_on():
        global SERPORT
        SERPORT.write(str(STIMULI_ON))

    def ser_send_off():
        global SERPORT
        SERPORT.write(str(STIMULI_OFF))

    def ser_quit():
        global SERPORT
        SERPORT.close()
        SERPORT = None
else:
    msg = 'serial port functionality not available'
    def ser_init(msg=msg):
        raise NotImplementedError(msg)

    def ser_send_on(msg=msg):
        raise NotImplementedError(msg)

    def ser_send_off(msg=msg):
        raise NotImplementedError(msg)

    def ser_quit(msg=msg):
        raise NotImplementedError(msg)

if available['parallel']:
    def par_init():
        global PARPORT
        PARPORT = parallel.Parallel()

    def par_send_on():
        global PARPORT
        PARPORT.setData(STIMULI_ON)

    def par_send_off():
        global PARPORT
        PARPORT.setData(STIMULI_OFF)

    def par_quit():
        global PARPORT
        PARPORT = None
else:
    msg = 'parallel port functionality not available'
    def par_init(msg=msg):
        raise NotImplementedError(msg)

    def par_send_on(msg=msg):
        raise NotImplementedError(msg)

    def par_send_off(msg=msg):
        raise NotImplementedError(msg)

    def par_quit(msg=msg):
        raise NotImplementedError(msg)
