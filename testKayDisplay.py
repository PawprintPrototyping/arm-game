import serial
import time
import pprint

#ser = serial.Serial('/dev/ttyKayDisplay', 115200)
with serial.Serial() as ser:
    #ser.rtscts = True
    #ser.dsrdtr = False
    ser.rts = False
    ser.dtr = False
    ser.baudrate = 115200
    ser.port = '/dev/ttyKayDisplay'
    #ser.setRTS(False)
    ser.open()
    #pprint.pprint(ser.get_settings())
    #time.sleep(3)
    print(ser.write(b'\xff123\xff\xff83\n'))
    #print(ser.write(b'81234567\n'))
    #time.sleep(3)
    #ser.rts = True
    #ser.dtr = True
    #time.sleep(1)
    #ser.rts = False
    #ser.dtr = False
    input(">")
