import hashlib
import time

def read_mines(filename):
    with open(filename, 'r') as file:
        return [line.strip() for line in file.readlines()]

def find_valid_pin(serial_number):
    pin = 0
    while True:
        temp_key = f"{serial_number}{pin}"
        hashed_key = hashlib.sha256(temp_key.encode()).hexdigest()
        if hashed_key.startswith("000000"):
            return pin
        pin += 1

def main():
    mines = read_mines("mines.txt")
    start_time = time.time()
    
    for mine in mines:
        pin = find_valid_pin(mine)
        print(f"Mine {mine} disarmed with PIN {pin}")
    
    end_time = time.time()
    print(f"Sequential Disarming Time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()