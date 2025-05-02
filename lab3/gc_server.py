import grpc
from concurrent import futures
import time
import os
import requests 
import json
import threading

import rover_pb2
import rover_pb2_grpc
import rabbitmq_utils

MAP_FILE = 'map1.txt'
MINES_FILE = 'mines.txt'
COMMANDS_API_URL = 'https://coe892.reev.dev/lab1/rover/' 

# File to log defused mines
DEFUSED_MINES_LOG = 'defused_mines.log'

def read_map(filename):
    """Reads the grid dimensions and grid from the map file."""
    with open(filename, 'r') as f:
        rows, cols = map(int, f.readline().split())
        grid = []
        for _ in range(rows):
            line = f.readline().split()
            grid.append([int(x) for x in line])
    return rows, cols, grid

def read_mines(filename):
    """Reads the mine serial numbers (one per line)."""
    with open(filename, 'r') as f:
        serials = [line.strip() for line in f]
    return serials

def read_commands(rover_id):
    """Fetches commands for the given rover from the API; returns a default string if not found."""
    url = f'{COMMANDS_API_URL}{rover_id}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("result"):
            # Filter out 'D' commands as rovers don't perform digging in Lab 3
            commands = data["data"]["moves"].strip()
            commands = commands.replace('D', '')
        else:
            print(f"Error in API response for rover {rover_id}: {data}")
            commands = "RMLMMMMMLMMRM"  # Default without 'D' commands
    except requests.RequestException as e:
        print(f"Error fetching commands for rover {rover_id}: {e}")
        commands = "RMLMMMMMLMMRM"  # Default without 'D' commands
    return commands

def handle_defused_mine(ch, method, properties, body):
    """Callback function for handling defused mine messages."""
    try:
        data = json.loads(body)
        print(f"Defused mine notification received: {data}")
        
        # Log to file
        with open(DEFUSED_MINES_LOG, 'a') as f:
            f.write(f"Mine defused at {data['coordinates']} by rover {data['rover_id']} with PIN {data['pin']}\n")
        
    except Exception as e:
        print(f"Error processing defused mine notification: {e}")

# Load data at server startup
MAP_ROWS, MAP_COLS, MAP_GRID = read_map(MAP_FILE)
MINES_SERIALS = read_mines(MINES_FILE)
COMMANDS_DICT = {rover_id: read_commands(rover_id) for rover_id in range(1, 11)}

class RoverServiceServicer(rover_pb2_grpc.RoverServiceServicer):
    def GetMap(self, request, context):
        """Returns the map (grid dimensions and flattened grid)."""
        flat_grid = [cell for row in MAP_GRID for cell in row]
        return rover_pb2.MapResponse(rows=MAP_ROWS, cols=MAP_COLS, grid=flat_grid)
    
    def GetCommands(self, request, context):
        """Streams out the command string for a given rover, one character at a time."""
        rover_id = request.rover_id
        commands = COMMANDS_DICT.get(rover_id, "RMLMMMMMLMMRM")  # Default without 'D' commands
        for cmd in commands:
            yield rover_pb2.Command(command=cmd)
            time.sleep(0.1)
     
    def GetMineSerial(self, request, context):
        """Returns a mine serial number based on the rover id."""
        rover_id = request.rover_id
        if 1 <= rover_id <= len(MINES_SERIALS):
            serial = MINES_SERIALS[rover_id - 1]
        else:
            serial = MINES_SERIALS[0]  # Default to first serial if out of range
        return rover_pb2.MineSerialResponse(serial=serial)
    
    def ReportStatus(self, request, context):
        """Receives and prints the status reported by a rover."""
        rover_id = request.rover_id
        success = request.success
        status = "SUCCESS" if success else "FAILURE"
        print(f"Rover {rover_id} reported status: {status}")
        return rover_pb2.StatusAck(message="Status received")

def start_defused_mines_listener():
    """Starts a separate thread to listen for defused mine notifications."""
    try:
        rabbitmq_utils.subscribe_to_defused_mines(handle_defused_mine)
    except Exception as e:
        print(f"Error in defused mines listener: {e}")

def serve():
    # Start the RabbitMQ listener in a separate thread
    listener_thread = threading.Thread(target=start_defused_mines_listener)
    listener_thread.daemon = True
    listener_thread.start()
    
    # Create an empty log file if it doesn't exist
    with open(DEFUSED_MINES_LOG, 'w') as f:
        f.write("=== Defused Mines Log ===\n")
    
    # Start the gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rover_pb2_grpc.add_RoverServiceServicer_to_server(RoverServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Ground Control gRPC server started on port 50051.")
    print("Listening for defused mine notifications...")
    
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()