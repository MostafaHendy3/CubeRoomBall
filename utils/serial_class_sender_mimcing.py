import serial
import time
import random
import os
import pty
import tty

# --- Configuration ---
# Use pseudo-terminal for communication with the receiver
VIRTUAL_PORT_SENDER = '/dev/pts/9'

# --- Data Generation Functions ---

def generate_format1_data() -> str:
    """Generates a random data string in Format 1."""
    status = random.choice(["ST", "US", "ST", "ST"]) # More likely to be stable
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
        time.sleep(0.5) # Pause between items
    yield "TOTAL\r\n"
    yield f"{i:04d}  {random.uniform(20.0, 50.0):.3f}\r\n" # Dummy total

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

if __name__ == "__main__":
    print("--- ST1 Scale Simulator ---")
    
    # Create pseudo-terminal pair
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)
    print(f"Created pseudo-terminal pair:")
    print(f"  Master: {master_fd}")
    print(f"  Slave: {slave_name}")
    print(f"  Receiver should use: {slave_name}")
    
    # Let the user choose which format to simulate
    while True:
        try:
            format_choice = int(input("Enter format to simulate (1, 2, 3, 4, or 5): "))
            if format_choice in [1, 2, 3, 4, 5]:
                break
            else:
                print("Invalid choice. Please enter 1, 2, 3, 4, or 5.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    try:
        print(f"Waiting for receiver to connect to {slave_name}...")
        print("Start the receiver script now and use the slave port shown above.")
        
        # Use the master end to write data
        with os.fdopen(master_fd, 'wb') as master:
            print(f"Simulator opened port {VIRTUAL_PORT_SENDER}. Sending data...")
            print("Run the main_application.py script now in another terminal.")
            print("Press Ctrl+C here to stop the simulator.")
            
            while True:
                if format_choice == 1:
                    data_to_send = generate_format1_data()
                    print(f"Sending: {data_to_send.strip()}")
                    print(f"Encoded bytes: {data_to_send.encode('ascii')}")
                    master.write(data_to_send.encode('ascii'))
                    master.flush()
                    time.sleep(1) # Send data every second

                elif format_choice == 2:
                    data_to_send = generate_format2_data()
                    print(f"Sending: {data_to_send.strip()}")
                    print(f"Encoded bytes: {data_to_send.encode('ascii')}")
                    master.write(data_to_send.encode('ascii'))
                    master.flush()
                    time.sleep(1)

                elif format_choice == 3:
                    print("\n--- Sending new Format 3 sequence ---")
                    for line in generate_format3_data_sequence():
                        print(f"Sending: {line.strip()}")
                        master.write(line.encode('ascii'))
                        master.flush()
                    print("--- Sequence finished. Waiting... ---\n")
                    time.sleep(5) # Wait before sending the next sequence

                elif format_choice == 4:
                    print("\n--- Sending new Format 4 ticket ---")
                    for line in generate_format4_data_sequence():
                        print(f"Sending: {line.strip()}")
                        master.write(line.encode('ascii'))
                        master.flush()
                    print("--- Ticket finished. Waiting... ---\n")
                    time.sleep(5)

                elif format_choice == 5:
                    data_to_send = generate_simple_int_data()
                    print(f"Sending: {data_to_send.strip()}")
                    print(f"Encoded bytes: {data_to_send.encode('ascii')}")
                    master.write(data_to_send.encode('ascii'))
                    master.flush()
                    time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
    finally:
        # Clean up file descriptors
        try:
            os.close(slave_fd)
            print("Cleaned up pseudo-terminal file descriptors")
        except OSError as e:
            print(f"Error cleaning up file descriptors: {e}")
