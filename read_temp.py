import board
import digitalio
import adafruit_max31855
import time
spi = board.SPI()
cs = digitalio.DigitalInOut(board.D5)

def read_temp():
    return adafruit_max31855.MAX31855(spi, cs).temperature

if __name__ == '__main__':
    while True:
        time.sleep(1)
        print('Temperature: {} degrees C'.format(read_temp()))