import serial
import time
import re

class ST1Scale:
    """
    A Python class to interface with the ST1 Weighing Scale via RS-232 serial communication.
    
    This class handles connecting, disconnecting, and parsing the various data formats
    as described in the ST1 User Manual.
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1):
        """
        Initializes the ST1Scale object.

        Args:
            port (str): The serial port name (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux).
            baudrate (int): The communication baud rate. The manual specifies various options,
                            with 9600 being a common default [cite: 175-183].
            timeout (int): The read timeout in seconds.
        """
        self.port_name = port
        self.baudrate = baudrate
        self.timeout = timeout
        
        # Communication parameters from the manual 
        self.serial_connection = serial.Serial()
        self.serial_connection.port = self.port_name
        self.serial_connection.baudrate = self.baudrate
        self.serial_connection.bytesize = serial.EIGHTBITS
        self.serial_connection.parity = serial.PARITY_NONE
        self.serial_connection.stopbits = serial.STOPBITS_ONE
        self.serial_connection.timeout = self.timeout
        
        self.is_connected = False

    def connect(self) -> bool:
        """
        Opens the serial port connection to the scale.
        
        Returns:
            bool: True if connection is successful, False otherwise.
        """
        if self.is_connected:
            print("Already connected.")
            return True
        try:
            self.serial_connection.open()
            self.is_connected = True
            print(f"Successfully connected to scale on {self.port_name}.")
            return True
        except serial.SerialException as e:
            print(f"Error: Could not connect to {self.port_name}. Details: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Closes the serial port connection."""
        if self.is_connected and self.serial_connection.is_open:
            self.serial_connection.close()
            self.is_connected = False
            print("Disconnected from scale.")

    def read_raw_line(self) -> str | None:
        """
        Reads a single raw line of data from the scale.
        Each data transmission is terminated by CR LF.
        
        Returns:
            str | None: The decoded string line, or None if no data is read.
        """
        if not self.is_connected:
            print("Not connected. Please call connect() first.")
            return None
        try:
            line_bytes = self.serial_connection.readline()
            # print(f"Raw line bytes: {line_bytes}")
            # print(f"Raw line: {line_bytes.decode('ascii')}")
            if line_bytes:
                return line_bytes.decode('ascii').strip()
            return "" # Return empty string on timeout
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")
            self.disconnect()
            return None

    def _parse_format1(self, line: str) -> dict:
        """
        Parses Format 1 data. [cite: 185, 222]
        Example: "ST, GS, + 1.000kg"
        """
        data = {'format': 1, 'raw': line, 'parsed_data': None}
        try:
            parts = line.split(',')
            if len(parts) >= 3:
                status_code = parts[0].strip()
                weight_type_code = parts[1].strip()
                weight_info = ','.join(parts[2:]).strip()
                
                # Use regex to find the numeric value and the unit
                # Handle the space between sign and number: "+ 1.000kg" or "- 1.000kg"
                match = re.search(r'([+\-])\s*(\d+\.\d+)\s*(\w+)', weight_info)
                if match:
                    sign = match.group(1)
                    number = match.group(2)
                    unit = match.group(3)
                    value = float(sign + number)  # Combine sign and number
                else:
                    value, unit = None, None

                data['parsed_data'] = {
                    'status_code': status_code,
                    'status': {"ST": "Stable", "US": "Unstable", "OL": "Overload"}.get(status_code, "Unknown"), # [cite: 224, 225]
                    'weight_type_code': weight_type_code,
                    'weight_type': {"GS": "Gross weight", "NT": "Net weight"}.get(weight_type_code, "Unknown"), # [cite: 227, 228]
                    'value': value,
                    'unit': unit
                }
        except Exception as e:
            data['error'] = str(e)
        return data

    def _parse_format2(self, line: str) -> dict:
        """
        Parses Format 2 data. [cite: 167, 186, 187, 189]
        Example: "+ 1.000kg"
        """
        data = {'format': 2, 'raw': line, 'parsed_data': None}
        try:
            # Handle the space between sign and number: "+ 1.000kg" or "- 1.000kg"
            match = re.search(r'([+\-])\s*(\d+\.\d+)\s*(\w+)', line)
            if match:
                sign = match.group(1)
                number = match.group(2)
                unit = match.group(3)
                value = float(sign + number)  # Combine sign and number
                data['parsed_data'] = {
                    'value': value,
                    'unit': unit
                }
        except Exception as e:
            data['error'] = str(e)
        return data
        
    def _parse_format3(self, line: str) -> dict:
        """
        Parses a single line of Format 3 data. [cite: 170, 171, 190]
        This format is multi-line (header, data, total).
        Examples: "S/N   WT/kg", "0001  2.205", "TOTAL", "0002  4.410"
        """
        data = {'format': 3, 'raw': line, 'parsed_data': None, 'line_type': 'unknown'}
        try:
            line = line.strip()
            if "S/N" in line and "WT" in line:
                data['line_type'] = 'header'
            elif "TOTAL" in line:
                data['line_type'] = 'total_header'
            else:
                parts = re.split(r'\s+', line)
                if len(parts) == 2:
                    # Heuristic: if the first part is all digits and the second can be a float,
                    # it could be a data line or a total value line.
                    if parts[0].isdigit() and re.match(r'^\d+(\.\d+)?$', parts[1]):
                        # This could be a data line OR the total line
                        data['line_type'] = 'data_or_total_value'
                        data['parsed_data'] = {
                            'column1': int(parts[0]), # Could be S/N or Total Count
                            'column2': float(parts[1]) # Could be Weight or Total Weight
                        }
        except Exception as e:
            data['error'] = str(e)
        return data

    def _parse_format4(self, line: str) -> dict:
        """
        Parses a single line of Format 4 data (ticket format). [cite: 172, 173, 199]
        This format is multi-line.
        """
        data = {'format': 4, 'raw': line, 'parsed_data': None, 'line_type': 'unknown'}
        try:
            line_upper = line.upper().strip()
            if line_upper.startswith("TICKET NO."):
                data['line_type'] = 'ticket_number'
                data['parsed_data'] = {'ticket_no': int(re.search(r'\d+', line).group())}
            elif line_upper.startswith("G"):
                data['line_type'] = 'gross_weight'
                match = re.search(r'(\d+\.\d+)\s*(\w+)', line)
                data['parsed_data'] = {'value': float(match.group(1)), 'unit': match.group(2)} if match else {}
            elif line_upper.startswith("T"):
                 # Distinguish between Tare weight and TOTAL
                if "TOTAL" not in line_upper:
                    data['line_type'] = 'tare_weight'
                    match = re.search(r'(\d+\.\d+)\s*(\w+)', line)
                    data['parsed_data'] = {'value': float(match.group(1)), 'unit': match.group(2)} if match else {}
            elif line_upper.startswith("N"):
                data['line_type'] = 'net_weight'
                match = re.search(r'(\d+\.\d+)\s*(\w+)', line)
                data['parsed_data'] = {'value': float(match.group(1)), 'unit': match.group(2)} if match else {}
            elif "TOTAL NUMBER" in line_upper:
                data['line_type'] = 'total_ticket_count_header'
            elif "OF TICKETS" in line_upper:
                data['line_type'] = 'total_ticket_count_value'
                data['parsed_data'] = {'count': int(re.search(r'\d+', line).group())}
            elif "TOTAL" in line_upper and "NET" in line_upper:
                data['line_type'] = 'total_net_header'
            elif re.match(r'^\s*\d+\.\d+\s*$', line): # Line with just a float value
                data['line_type'] = 'total_net_value'
                data['parsed_data'] = {'total_net': float(line.strip())}
        except Exception as e:
            data['error'] = str(e)
        return data
        
    def read_parsed_data(self, data_format: int) -> dict | None:
        """
        Reads a line from the scale and parses it based on the specified format.
        
        Args:
            data_format (int): The format number (1, 2, 3, or 4) to use for parsing.
                               This must match the scale's UF-6 setting.

        Returns:
            dict | None: A dictionary containing the parsed data, or None on error.
        """
        line = self.read_raw_line()
        # print(f"Raw line: {line}")
        if line is None:
            return None # Error reading
        if line == "":
            return {} # Timeout, no data
            
        if data_format == 1:
            return self._parse_format1(line)
        elif data_format == 2:
            return self._parse_format2(line)
        elif data_format == 3:
            return self._parse_format3(line)
        elif data_format == 4:
            return self._parse_format4(line)
        else:
            print(f"Error: Unknown data format '{data_format}'.")
            return {'raw': line, 'error': f'Unknown format {data_format}'}

# --- Example Usage ---
if __name__ == "__main__":
    # Use pseudo-terminal - the sender will create the pair and show the slave port
    # You need to update this with the actual slave port shown by the sender
    SCALE_PORT = '/dev/pts/13'  # This will be updated by the sender
    
    # IMPORTANT: Set this to match the format you configured in the scale's UF-6 menu.
    # For this example, we assume the scale is set to "232 2" (Stream output - Format 1).
    DATA_FORMAT_TO_TEST = 1 

    # Initialize the scale object
    scale = ST1Scale(port=SCALE_PORT, baudrate=9600, timeout=1)

    # Connect to the scale with retry loop
    print(f"Attempting to connect to scale on {SCALE_PORT}...")
    print("Waiting for sender to be ready...")
    print("Make sure to run the sender script (serial_class_sender_mimcing.py) in another terminal.")
    print("The sender will create a pseudo-terminal pair and show you the slave port to use.")
    print("Update SCALE_PORT in this script with the slave port shown by the sender.")
    
    while True:
        if scale.connect():
            print("\nSuccessfully connected to scale!")
            print("Reading data from scale...")
            print(f"Expecting data in Format {DATA_FORMAT_TO_TEST}. Press Ctrl+C to exit.\n")
            
            try:
                while True:
                    # Read and parse the data
                    parsed_data = scale.read_parsed_data(data_format=DATA_FORMAT_TO_TEST)
                    
                    if parsed_data: # Check if dictionary is not empty
                        print(parsed_data['parsed_data'].get('value', 'No value'))

                    time.sleep(0.2) # Wait a bit before the next read
            
            except KeyboardInterrupt:
                print("\nStopping...")
                break
            
            finally:
                # Always disconnect cleanly
                scale.disconnect()
            break
        else:
            print("Connection failed. Retrying in 2 seconds...")
            time.sleep(2)