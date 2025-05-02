import grpc
from concurrent import futures
import time
import os
import requests 
import json  

import rover_pb2
import rover_pb2_grpc

MAP_FILE = 'map1.txt'
MINES_FILE = 'mines.txt'
COMMANDS_API_URL = 'https://coe892.reev.dev/lab1/rover/' 

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
            commands = data["data"]["moves"].strip()
        else:
            print(f"Error in API response for rover {rover_id}: {data}")
            commands = "RMLMMMMMDLMMRMD"
    except requests.RequestException as e:
        print(f"Error fetching commands for rover {rover_id}: {e}")
        # Default command string (if API call fails)
        commands = "RMLMMMMMDLMMRMD"
    return commands

# Load data at server startup.
MAP_ROWS, MAP_COLS, MAP_GRID = read_map(MAP_FILE)
MINES_SERIALS = read_mines(MINES_FILE)
COMMANDS_DICT = {rover_id: read_commands(rover_id) for rover_id in range(1, 11)}

# Moveset 11 where the rover should be successful at finishing the map
COMMANDS_DICT[11] = "MDMDMDLMDLMDMDMDRMDRMDMDMD"

class RoverServiceServicer(rover_pb2_grpc.RoverServiceServicer):
    def GetMap(self, request, context):
        """Returns the map (grid dimensions and flattened grid)."""
        flat_grid = [cell for row in MAP_GRID for cell in row]
        return rover_pb2.MapResponse(rows=MAP_ROWS, cols=MAP_COLS, grid=flat_grid)
    
    def GetCommands(self, request, context):
        """Streams out the command string for a given rover, one character at a time."""
        rover_id = request.rover_id
        commands = COMMANDS_DICT.get(rover_id, "RMLMMMMMDLMMRMD")
        for cmd in commands:
            yield rover_pb2.Command(command=cmd)
            time.sleep(0.1)
     
    def GetMineSerial(self, request, context):
        """Returns a mine serial number based on the rover id."""
        rover_id = request.rover_id
        if 1 <= rover_id <= len(MINES_SERIALS):
            serial = MINES_SERIALS[rover_id - 1]
        else:
            serial = ""
        return rover_pb2.MineSerialResponse(serial=serial)
    
    def ReportStatus(self, request, context):
        """Receives and prints the status reported by a rover."""
        rover_id = request.rover_id
        success = request.success
        status = "SUCCESS" if success else "FAILURE"
        print(f"Rover {rover_id} reported status: {status}")
        return rover_pb2.StatusAck(message="Status received")
    
    def ShareMinePin(self, request, context):
        """Receives and prints the mine PIN computed by a rover."""
        rover_id = request.rover_id
        pin = request.pin
        print(f"Rover {rover_id} shared mine PIN: {pin}")
        return rover_pb2.PinAck(message="PIN received")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rover_pb2_grpc.add_RoverServiceServicer_to_server(RoverServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Ground Control gRPC server started on port 50051.")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()