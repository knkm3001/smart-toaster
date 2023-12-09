import time
from typing import Final
import RPi.GPIO as GPIO

GPIO_PIN:Final[int] = 14
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIN,GPIO.OUT)

def gpio_creanup():
    GPIO.cleanup()

def gpio_control(power:bool):
    if power:
        GPIO.output(GPIO_PIN,GPIO.HIGH)
    else:
        GPIO.output(GPIO_PIN,GPIO.LOW)

if __name__ == '__main__':
    # for debug
    print("run ssr for debug.")
    interval_time = 2
    try:
        while True:
            gpio_control(power=True)
            print("power on.")
            time.sleep(interval_time)
            gpio_control(power=False)
            print("power off.")
            time.sleep(interval_time)
    except KeyboardInterrupt:
        gpio_control(power=False)
        gpio_creanup()
        print("\nssr done.")