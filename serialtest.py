import serial

port = serial.Serial(0)
print port.portstr

test_msg = 'hello EEG machine'
port.write(test_msg)
port.close()
