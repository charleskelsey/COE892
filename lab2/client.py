import sys
import grpc
import time
import hashlib

import rover_pb2
import rover_pb2_grpc

def find_pin(serial):
    """Computes a PIN for the mine using a brute-force search on SHA256 hashes.
       (Searches for a hash that starts with six zeros.)"""
    pin = 0
    while True:
        temp_key = serial + str(pin)
        hash_hex = hashlib.sha256(temp_key.encode()).hexdigest()
        if hash_hex.startswith('000000'):
            return pin
        pin += 1

def get_map(stub):
    """Retrieves the map from the server and reconstructs the 2D grid."""
    empty = rover_pb2.Empty()
    response = stub.GetMap(empty)
    rows = response.rows
    cols = response.cols
    flat_grid = response.grid
    grid = []
    for i in range(rows):
        row = flat_grid[i*cols:(i+1)*cols]
        grid.append(list(row))
    return rows, cols, grid

def process_commands(rover_id, grid, rows, cols, stub):
    """
    Processes the command stream.
    - When moving (M): if the rover is already on an active mine (on_mine is True) then it explodes
      because the rover is leaving the mine without disarming.
    - Turning left or right (L or R) does not change position.
    - When disarming (D): if the rover is on an active mine, disarm it and set on_mine to False.
    - Out-of-bound moves are ignored (rover stays in the same spot).
    """
    directions = ['N', 'E', 'S', 'W']
    direction_idx = 2  # starting facing South
    current_pos = (0, 0)
    visited = set([current_pos])
    exploded = False
    on_mine = False  # True when rover is on an active mine

    command_stream = stub.GetCommands(rover_pb2.RoverRequest(rover_id=rover_id))
    for command_msg in command_stream:
        cmd = command_msg.command
        print(f"Rover {rover_id} executing command: {cmd}")

        if cmd == 'L':
            direction_idx = (direction_idx - 1) % 4
        elif cmd == 'R':
            direction_idx = (direction_idx + 1) % 4
        elif cmd == 'M':
            # If we are on an active mine and then try to move without disarming, we explode.
            if on_mine:
                print(f"Rover {rover_id} is leaving an active mine without disarming at {current_pos}!")
                exploded = True
                break

            # Execute the move.
            dr, dc = 0, 0
            current_dir = directions[direction_idx]
            if current_dir == 'N':
                dr = -1
            elif current_dir == 'S':
                dr = 1
            elif current_dir == 'E':
                dc = 1
            elif current_dir == 'W':
                dc = -1
            new_row = current_pos[0] + dr
            new_col = current_pos[1] + dc

            # Instead of exploding, if out-of-bounds just ignore the move.
            if 0 <= new_row < rows and 0 <= new_col < cols:
                current_pos = (new_row, new_col)
                visited.add(current_pos)
                print(f"Rover {rover_id} moved to position: {current_pos}")
                # Update on_mine state after moving.
                r, c = current_pos
                if grid[r][c] > 0:
                    print(f"Rover {rover_id} has landed on an active mine at {current_pos}!")
                    on_mine = True
                else:
                    on_mine = False
            else:
                print("Movement out of bounds! Staying at the same position.")
                # Do not update current_pos; ignore the move.
                continue

        elif cmd == 'D':
            # Disarming command: only works if we are on an active mine.
            r, c = current_pos
            print(f"Rover {rover_id} attempting to disarm mine at position {current_pos}")
            if grid[r][c] > 0 and on_mine:
                # Get mine serial from the server.
                mine_serial_response = stub.GetMineSerial(rover_pb2.MineSerialRequest(rover_id=rover_id))
                serial = mine_serial_response.serial
                print(f"Rover {rover_id} received mine serial: {serial}")
                # Compute the PIN.
                pin = find_pin(serial)
                print(f"Rover {rover_id} computed mine PIN: {pin}")
                # Share the PIN with the server.
                pin_ack = stub.ShareMinePin(rover_pb2.MinePin(rover_id=rover_id, pin=pin))
                print(f"Server acknowledgement: {pin_ack.message}")
                # Mark the mine as disarmed locally and reset on_mine state.
                grid[r][c] = 0
                on_mine = False
            else:
                print("No active mine to disarm at current position.")
        else:
            print(f"Unknown command: {cmd}")

        time.sleep(0.1)

    # Report the status to the server once.
    status_report = rover_pb2.StatusReport(rover_id=rover_id, success=not exploded)
    stub.ReportStatus(status_report)
    return visited, exploded

def write_path(rover_id, visited, rows, cols):
    """Writes a grid showing the visited positions to a file."""
    path_grid = [['0' for _ in range(cols)] for _ in range(rows)]
    for (r, c) in visited:
        path_grid[r][c] = '*'
    with open(f'path_{rover_id}.txt', 'w') as f:
        for row in path_grid:
            f.write(' '.join(row) + '\n')
    print(f"Rover {rover_id} path written to path_{rover_id}.txt")

def main():
    if len(sys.argv) != 2:
        print("Usage: python client.py <rover_id (1-11)>")
        sys.exit(1)
    rover_id = int(sys.argv[1])
    if not (1 <= rover_id <= 11):
        print("Rover id must be between 1 and 11.")
        sys.exit(1)
    
    # Connect to the gRPC server.
    channel = grpc.insecure_channel('localhost:50051')
    stub = rover_pb2_grpc.RoverServiceStub(channel)
    
    # 1. Retrieve the map.
    rows, cols, grid = get_map(stub)
    print(f"Rover {rover_id} received map of size {rows}x{cols}")
    
    # 2. Process the command stream.
    visited, exploded = process_commands(rover_id, grid, rows, cols, stub)
    
    # 3. Write the visited path to a file.
    write_path(rover_id, visited, rows, cols)

if __name__ == '__main__':
    main()