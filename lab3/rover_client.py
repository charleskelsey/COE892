import sys
import grpc
import time
import hashlib

import rover_pb2
import rover_pb2_grpc
import rabbitmq_utils

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
    - Moving (M): rover moves to new position unless out of bounds
    - Turning left or right (L or R) changes direction
    - When rover finds a mine, it publishes to the Demine-Queue channel
    """
    directions = ['N', 'E', 'S', 'W']
    direction_idx = 2  # starting facing South
    current_pos = (0, 0)
    visited = set([current_pos])
    exploded = False

    command_stream = stub.GetCommands(rover_pb2.RoverRequest(rover_id=rover_id))
    for command_msg in command_stream:
        cmd = command_msg.command
        print(f"Rover {rover_id} executing command: {cmd}")

        if cmd == 'L':
            direction_idx = (direction_idx - 1) % 4
            print(f"Rover {rover_id} turned left, now facing {directions[direction_idx]}")
            
        elif cmd == 'R':
            direction_idx = (direction_idx + 1) % 4
            print(f"Rover {rover_id} turned right, now facing {directions[direction_idx]}")
            
        elif cmd == 'M':
            # Execute the move
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

            # Check if move is within bounds
            if 0 <= new_row < rows and 0 <= new_col < cols:
                current_pos = (new_row, new_col)
                visited.add(current_pos)
                print(f"Rover {rover_id} moved to position: {current_pos}")
                
                # Check if we've found a mine
                r, c = current_pos
                if grid[r][c] > 0:
                    print(f"Rover {rover_id} found a mine at {current_pos}!")
                    
                    # Get mine serial from the server
                    mine_serial_response = stub.GetMineSerial(rover_pb2.MineSerialRequest(rover_id=rover_id))
                    serial = mine_serial_response.serial
                    print(f"Rover {rover_id} received mine serial: {serial}")
                    
                    # Publish demine task to RabbitMQ
                    rabbitmq_utils.publish_demine_task(current_pos, rover_id, serial)
                    print(f"Rover {rover_id} published demine task for mine at {current_pos}")
                    
                    # Set the mine cell to 0 in our local grid to prevent re-publishing
                    grid[r][c] = 0
            else:
                print("Movement out of bounds! Staying at the same position.")
        else:
            print(f"Unknown command: {cmd}")

        time.sleep(0.1)

    # Report the status to the server once
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
        print("Usage: python rover_client.py <rover_id (1-10)>")
        sys.exit(1)
    rover_id = int(sys.argv[1])
    if not (1 <= rover_id <= 10):
        print("Rover id must be between 1 and 10.")
        sys.exit(1)
    
    # Connect to the gRPC server
    channel = grpc.insecure_channel('localhost:50051')
    stub = rover_pb2_grpc.RoverServiceStub(channel)
    
    # 1. Retrieve the map
    rows, cols, grid = get_map(stub)
    print(f"Rover {rover_id} received map of size {rows}x{cols}")
    
    # 2. Process the command stream and publish demine tasks
    visited, exploded = process_commands(rover_id, grid, rows, cols, stub)
    
    # 3. Write the visited path to a file
    write_path(rover_id, visited, rows, cols)
    
    print(f"Rover {rover_id} finished execution.")

if __name__ == '__main__':
    main()