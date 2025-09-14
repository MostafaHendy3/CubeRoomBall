import serial
import time
import random
import os
import sys
import threading
from typing import Optional

# --- Windows-specific Configuration ---
# Windows COM port configuration
# Note: For Windows, you can use:
# 1. Physical COM ports (COM1, COM2, etc.)
# 2. Virtual COM ports using tools like:
#    - com0com (free): https://sourceforge.net/projects/com0com/
#    - Virtual Serial Port Driver (paid)
#    - com2tcp for network-based virtual ports

# Default Windows COM ports - modify as needed
WINDOWS_COM_PORTS = {
    'sender': 'COM37',    # Port for sending data
    'receiver': 'COM38'   # Port for receiving data (inform your receiver application)
}

# --- Data Generation Functions ---

def generate_format1_data() -> str:
    """Generates a random data string in Format 1."""
    status = random.choice(["ST", "US", "ST", "ST"])  # More likely to be stable
    weight_type = random.choice(["GS", "NT"])
    weight = random.uniform(1.0, 100.0)
    sign = random.choice(["+"])
    unit = "kg"
    # Note: The manual shows a space between sign and number.
    return f"{status}, {weight_type}, {sign} {weight:.3f}{unit}\r\n"

def generate_format2_data() -> str:
    """Generates a random data string in Format 2."""
    weight = random.uniform(0.5, 100.0)
    sign = random.choice(["+", "-"])
    unit = "kg"
    return f"{sign} {weight:.3f}{unit}\r\n"

def generate_format3_data_sequence():
    """Generator function that yields lines for a Format 3 sequence."""
    yield "S/N   WT/kg\r\n"
    for i in range(1, random.randint(3, 6)):
        yield f"{i:04d}  {random.uniform(1.0, 5.0):.3f}\r\n"
        time.sleep(0.5)  # Pause between items
    yield "TOTAL\r\n"
    yield f"{i:04d}  {random.uniform(20.0, 50.0):.3f}\r\n"  # Dummy total

def generate_format4_data_sequence():
    """Generator function that yields lines for a Format 4 ticket."""
    ticket_no = random.randint(100, 200)
    gross = random.uniform(10.0, 15.0)
    tare = random.uniform(1.0, 2.0)
    net = gross - tare
    yield f"TICKET NO. {ticket_no:04d}\r\n"
    time.sleep(0.2)
    yield f"G    {gross:.3f}kg\r\n"
    time.sleep(0.2)
    yield f"T    {tare:.3f}kg\r\n"
    time.sleep(0.2)
    yield f"N    {net:.3f}kg\r\n"

def generate_simple_int_data() -> str:
    """Generates a random integer data string."""
    return f"{random.randint(1, 100)}\r\n"

def list_available_com_ports():
    """List available COM ports on Windows."""
    import serial.tools.list_ports
    
    ports = list(serial.tools.list_ports.comports())
    if ports:
        print("\nAvailable COM ports on this system:")
        for port, desc, hwid in sorted(ports):
            print(f"  {port}: {desc} [{hwid}]")
    else:
        print("\nNo COM ports found on this system.")
    
    return [port.device for port, _, _ in ports]

def setup_virtual_com_ports_guide():
    """Display guide for setting up virtual COM ports on Windows."""
    print("\n" + "="*60)
    print("WINDOWS VIRTUAL COM PORT SETUP GUIDE")
    print("="*60)
    print("""
For testing without physical serial devices, you need virtual COM ports:

OPTION 1: com0com (FREE, Recommended)
   1. Download: https://sourceforge.net/projects/com0com/
   2. Install com0com
   3. Run 'Setup Command Prompt' as Administrator
   4. Create pair: setupc install PortName=COM3 PortName=COM4
   5. This creates COM3 <-> COM4 pair (data sent to COM3 appears on COM4)

OPTION 2: Virtual Serial Port Driver (PAID)
   1. Download from Eltima Software
   2. Create virtual COM port pairs
   3. Configure as needed

OPTION 3: Use Physical COM Ports
   1. Connect two physical COM ports with a null modem cable
   2. Or use USB-to-Serial adapters

OPTION 4: Network-based (Advanced)
   1. Use com2tcp for network-based virtual ports
   2. Suitable for remote testing

CURRENT CONFIGURATION:
   Sender Port:   {sender}
   Receiver Port: {receiver}
   
WARNING: Make sure your receiver application connects to: {receiver}
""".format(
        sender=WINDOWS_COM_PORTS['sender'],
        receiver=WINDOWS_COM_PORTS['receiver']
    ))

def get_user_com_port_config():
    """Allow user to configure COM ports."""
    print("\nCOM Port Configuration")
    print("-" * 30)
    
    # List available ports
    available_ports = list_available_com_ports()
    
    # Get sender port
    while True:
        sender_port = input(f"\nEnter sender COM port (default: {WINDOWS_COM_PORTS['sender']}): ").strip().upper()
        if not sender_port:
            sender_port = WINDOWS_COM_PORTS['sender']
        
        if sender_port.startswith('COM') or sender_port in available_ports:
            break
        else:
            print("ERROR: Invalid COM port format. Use format like COM1, COM2, etc.")
    
    # Get receiver port
    while True:
        receiver_port = input(f"Enter receiver COM port (default: {WINDOWS_COM_PORTS['receiver']}): ").strip().upper()
        if not receiver_port:
            receiver_port = WINDOWS_COM_PORTS['receiver']
        
        if receiver_port.startswith('COM') or receiver_port in available_ports:
            if receiver_port == sender_port:
                print("ERROR: Receiver port cannot be the same as sender port!")
                continue
            break
        else:
            print("ERROR: Invalid COM port format. Use format like COM1, COM2, etc.")
    
    return sender_port, receiver_port

def test_com_port_connection(port: str) -> bool:
    """Test if a COM port can be opened."""
    try:
        with serial.Serial(port, 9600, timeout=1) as ser:
            return True
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {port}: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error with {port}: {e}")
        return False

class WindowsSerialSimulator:
    """Windows-compatible serial simulator class."""
    
    def __init__(self, sender_port: str, receiver_port: str):
        self.sender_port = sender_port
        self.receiver_port = receiver_port
        self.serial_connection: Optional[serial.Serial] = None
        self.running = False
    
    def connect(self) -> bool:
        """Establish serial connection."""
        try:
            print(f"\nAttempting to connect to {self.sender_port}...")
            
            self.serial_connection = serial.Serial(
                port=self.sender_port,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            print(f"SUCCESS: Successfully connected to {self.sender_port}")
            print(f"INFO: Receiver should connect to: {self.receiver_port}")
            return True
            
        except serial.SerialException as e:
            print(f"ERROR: Failed to connect to {self.sender_port}: {e}")
            return False
        except Exception as e:
            print(f"ERROR: Unexpected connection error: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection."""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            print(f"INFO: Disconnected from {self.sender_port}")
    
    def send_data(self, data: str):
        """Send data through serial port."""
        if not self.serial_connection or not self.serial_connection.is_open:
            print("ERROR: Serial connection not open!")
            return False
        
        try:
            encoded_data = data.encode('ascii')
            bytes_written = self.serial_connection.write(encoded_data)
            self.serial_connection.flush()
            
            print(f"SENT: {data.strip()}")
            print(f"      Bytes: {encoded_data} ({bytes_written} bytes)")
            return True
            
        except Exception as e:
            print(f"ERROR: Error sending data: {e}")
            return False
    
    def run_simulation(self, format_choice: int):
        """Run the simulation loop."""
        if not self.connect():
            return
        
        self.running = True
        print(f"\nStarting Format {format_choice} simulation...")
        print("INFO: Make sure your receiver application is connected to:", self.receiver_port)
        print("INFO: Press Ctrl+C to stop the simulator")
        print("-" * 50)
        
        try:
            while self.running:
                if format_choice == 1:
                    data = generate_format1_data()
                    self.send_data(data)
                    time.sleep(1)
                
                elif format_choice == 2:
                    data = generate_format2_data()
                    self.send_data(data)
                    time.sleep(1)
                
                elif format_choice == 3:
                    print("\nSending new Format 3 sequence...")
                    for line in generate_format3_data_sequence():
                        if not self.running:
                            break
                        self.send_data(line)
                    print("INFO: Sequence finished. Waiting...\n")
                    time.sleep(5)
                
                elif format_choice == 4:
                    print("\nSending new Format 4 ticket...")
                    for line in generate_format4_data_sequence():
                        if not self.running:
                            break
                        self.send_data(line)
                    print("INFO: Ticket finished. Waiting...\n")
                    time.sleep(5)
                
                elif format_choice == 5:
                    data = generate_simple_int_data()
                    self.send_data(data)
                    time.sleep(1)
        
        except KeyboardInterrupt:
            print("\nINFO: Simulator stopped by user")
        except Exception as e:
            print(f"\nERROR: Simulation error: {e}")
        finally:
            self.running = False
            self.disconnect()

def main():
    """Main function for Windows serial simulator."""
    print("=" * 60)
    print("ST1 Scale Simulator - Windows Version")
    print("=" * 60)
    print("Windows Serial Communication Simulator")
    print("Simulates various scale data formats over COM ports")
    
    # Check if running on Windows
    if os.name != 'nt':
        print("\nWARNING: This is the Windows version of the simulator.")
        print("         For Linux/Unix systems, use the original script with pty.")
        response = input("\nContinue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Exiting...")
            return
    
    # Show setup guide
    setup_virtual_com_ports_guide()
    
    # Get COM port configuration
    sender_port, receiver_port = get_user_com_port_config()
    
    # Test sender port
    print(f"\nTesting connection to {sender_port}...")
    if not test_com_port_connection(sender_port):
        print(f"\nERROR: Cannot connect to {sender_port}")
        print("Troubleshooting tips:")
        print("   1. Make sure the COM port exists")
        print("   2. Install virtual COM port software (com0com)")
        print("   3. Check if another application is using the port")
        print("   4. Run as Administrator if needed")
        return
    
    # Get format choice
    while True:
        print("\nAvailable Data Formats:")
        print("   1. Format 1: ST, GS, + 12.345kg")
        print("   2. Format 2: + 12.345kg")
        print("   3. Format 3: Multi-line sequence")
        print("   4. Format 4: Ticket format")
        print("   5. Format 5: Simple integer")
        
        try:
            format_choice = int(input("\nEnter format to simulate (1-5): "))
            if format_choice in [1, 2, 3, 4, 5]:
                break
            else:
                print("ERROR: Invalid choice. Please enter 1, 2, 3, 4, or 5.")
        except ValueError:
            print("ERROR: Invalid input. Please enter a number.")
    
    # Create and run simulator
    simulator = WindowsSerialSimulator(sender_port, receiver_port)
    simulator.run_simulation(format_choice)
    
    print("\nSimulator finished. Goodbye!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        input("Press Enter to exit...")