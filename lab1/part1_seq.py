import requests
import time

def read_map(filename):
    with open(filename, 'r') as file:
        lines = file.readlines()
    rows, cols = map(int, lines[0].split())
    land_map = [list(map(int, line.split())) for line in lines[1:]]
    return rows, cols, land_map

def fetch_rover_commands(rover_id):
    url = f"https://coe892.reev.dev/lab1/rover/{rover_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text.strip()
    else:
        return ""  # Return empty string if API call fails

def move_rover(commands, land_map):
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # S, E, N, W
    x, y, dir_idx = 0, 0, 0  # Start at (0,0) facing South
    path_map = [[0] * len(land_map[0]) for _ in range(len(land_map))]
    
    for cmd in commands:
        if cmd == 'L':
            dir_idx = (dir_idx - 1) % 4
        elif cmd == 'R':
            dir_idx = (dir_idx + 1) % 4
        elif cmd == 'M':
            new_x, new_y = x + directions[dir_idx][0], y + directions[dir_idx][1]
            if 0 <= new_x < len(land_map) and 0 <= new_y < len(land_map[0]):
                if land_map[new_x][new_y] == 0:
                    x, y = new_x, new_y
                else:
                    break  # Rover hits a mine and stops
        elif cmd == 'D':
            if land_map[x][y] != 0:
                land_map[x][y] = 0
    
    path_map[x][y] = '*'
    
    return path_map

def save_path(filename, path_map):
    with open(filename, 'w') as file:
        for row in path_map:
            file.write(' '.join(str(cell) for cell in row) + '\n')

def main():
    rows, cols, land_map = read_map("map1.txt")
    start_time = time.time()
    
    for rover_id in range(1, 11):
        commands = fetch_rover_commands(rover_id)
        print(f"Rover {rover_id} commands: {commands}")
        path_map = move_rover(commands, [row[:] for row in land_map])
        save_path(f"path_{rover_id}.txt", path_map)
    
    end_time = time.time()
    print(f"Sequential Execution Time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()