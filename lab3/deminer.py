import sys
import json
import time
import hashlib
import threading
import rabbitmq_utils

class Deminer:
    def __init__(self, deminer_id):
        self.deminer_id = deminer_id
        self.busy = False
        self.current_task = None
    
    def find_pin(self, serial):
        """Computes a PIN for the mine using a brute-force search on SHA256 hashes."""
        pin = 0
        while True:
            temp_key = serial + str(pin)
            hash_hex = hashlib.sha256(temp_key.encode()).hexdigest()
            if hash_hex.startswith('000000'):
                return pin
            pin += 1
    
    def process_demine_task(self, ch, method, properties, body):
        """Callback function for processing demine tasks."""
        # If already busy, ignore the task
        if self.busy:
            print(f"Deminer {self.deminer_id} is busy, ignoring new task")
            return
        
        try:
            self.busy = True
            data = json.loads(body)
            self.current_task = data
            
            coordinates = data['coordinates']
            rover_id = data['rover_id']
            serial = data['serial']
            
            print(f"Deminer {self.deminer_id} processing task: Mine at {coordinates} from rover {rover_id}")
            
            # Simulate demining work
            print(f"Deminer {self.deminer_id} computing PIN for mine with serial: {serial}")
            
            # Start demining in a separate thread to not block RabbitMQ consumer
            threading.Thread(target=self.demine_task, args=(coordinates, rover_id, serial)).start()
            
        except Exception as e:
            print(f"Error processing demine task: {e}")
            self.busy = False
    
    def demine_task(self, coordinates, rover_id, serial):
        """Performs the actual demining work."""
        try:
            # Compute the PIN
            pin = self.find_pin(serial)
            print(f"Deminer {self.deminer_id} computed PIN {pin} for mine at {coordinates}")
            
            # Publish the result
            rabbitmq_utils.publish_defused_mine(coordinates, rover_id, serial, pin)
            print(f"Deminer {self.deminer_id} published defused mine notification")
            
            # Set deminer back to not busy
            self.busy = False
            self.current_task = None
            
        except Exception as e:
            print(f"Error during demining: {e}")
            self.busy = False
            self.current_task = None

def main():
    if len(sys.argv) != 2:
        print("Usage: python deminer.py <deminer_id (1-2)>")
        sys.exit(1)
    
    deminer_id = int(sys.argv[1])
    if not (1 <= deminer_id <= 2):
        print("Deminer id must be 1 or 2.")
        sys.exit(1)
    
    print(f"Starting Deminer {deminer_id}")
    deminer = Deminer(deminer_id)
    
    # Subscribe to the demine queue and start processing tasks
    try:
        rabbitmq_utils.subscribe_to_demine_queue(deminer.process_demine_task)
    except KeyboardInterrupt:
        print(f"Deminer {deminer_id} stopped")

if __name__ == '__main__':
    main()