import time
import serial
from queue import Queue
import hx711 as HX711
from datetime import datetime
import threading

class DirectWeightSensor:
    """Interface for HX711 weight sensor directly connected to GPIO pins"""
    def __init__(self,dout,pd_sck,reference_unit=1):
        print("Initializing direct HX711 scale...")
        self.hx=HX711.HX711(dout,pd_sck)
        self.hx.set_reading_format("MSB","MSB")
        self.hx.set_reference_unit(reference_unit)
        self.hx.reset()
        self.tare()
    
    def get_weight(self):
        """Get weight reading from HX711"""
        weight=self.hx.get_weight(5)
        self.hx.power_down()
        self.hx.power_up()
        return weight
    
    def tare(self):
        """Tare the scale"""
        self.hx.tare()
        print("Scale tared! Waiting for birds...")
    
    def close(self):
        """Clean shutdown of HX711"""
        self.hx.power_down()


class SerialWeightSensor:
    """Interface for Pico weight sensor over serial USB"""
    
    def __init__(self, port, baudrate=115200, timeout=2.0):
        print("Initializing Pico serial weight sensor...")
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.latest_weight = None
        self.connected = False
        self.reader_thread = None
        self.running = False
        self.tare_confirmed = threading.Event()
        self.connect()
    
    def connect(self):
        """Connect to Pico serial port"""
        try:
            print(f"Connecting to Pico on {self.port}...")
            self.serial = serial.Serial()
            self.serial.port = self.port
            self.serial.baudrate = self.baudrate
            self.serial.timeout = 1.0
            self.serial.dtr = False  # Prevent reset on connect
            self.serial.open()
            
            # Don't clear the buffer - we want to catch whatever the Pico sends
            # time.sleep(2)  # Remove or reduce this
            # self.serial.reset_input_buffer()  # Remove this
            
            # Wait for any valid message from Pico
            start_time = time.time()
            while time.time() - start_time < 5:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    print(f"DEBUG: Received from Pico: '{line}'")
                    if line.startswith("WEIGHT:") or line.startswith("TARED") or line == "READY" or line.startswith("TARING"):
                        print("Pico weight sensor ready!")
                        self.connected = True
                        break
                time.sleep(0.1)
        except Exception as e:
            print(f"Failed to connect to Pico: {e}")
            self.connected = False
            raise
    
    def _read_loop(self):
        """Background thread to continuously read weight from serial"""
        while self.running:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    
                    if line.startswith("WEIGHT:"):
                        try:
                            weight = float(line.split(":")[1])
                            self.latest_weight = weight
                        except ValueError:
                            pass
                    
                    elif line.startswith("TARED"):
                        print(f"Pico: Scale tared - {line}")
                        self.tare_confirmed.set()  # Signal tare() that we're done
                    
                    elif line == "TARING":
                        print("Pico: Taring scale...")
                    
                    elif line.startswith("ERROR:"):
                        error = line.split(":")[1]
                        if error != "NO_READING":
                            print(f"Pico error: {error}")
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Serial read error: {e}")
                time.sleep(0.1)
    
    def get_weight(self):
        """Get latest weight reading"""
        return self.latest_weight
    
    def tare(self):
        """Send tare command to Pico"""
        if self.serial and self.serial.is_open:
            self.tare_confirmed.clear()
            self.serial.write(b'TARE\n')
            # Wait for reader thread to see TARED response
            if self.tare_confirmed.wait(timeout=2.0):
                return True
            print("Warning: Tare confirmation timeout")
        return False
    
    def close(self):
        """Clean shutdown of serial connection"""
        self.running = False
        if self.reader_thread:
            self.reader_thread.join(timeout=1)
        if self.serial:
            self.serial.close()
        print("Serial connection closed")
