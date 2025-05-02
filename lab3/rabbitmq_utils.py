import pika
import json

# RabbitMQ connection parameters
RABBITMQ_HOST = 'localhost'
DEMINE_QUEUE = 'Demine-Queue'
DEFUSED_MINES = 'Defused-Mines'

def get_connection():
    """Establishes and returns a connection to RabbitMQ server"""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        return connection
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Failed to connect to RabbitMQ: {e}")
        raise

def publish_demine_task(coordinates, rover_id, serial):
    """Publishes a demine task to the Demine-Queue channel"""
    try:
        connection = get_connection()
        channel = connection.channel()
        
        # Declare the queue (creates if doesn't exist)
        channel.queue_declare(queue=DEMINE_QUEUE)
        
        # Create message payload
        message = {
            'coordinates': coordinates,
            'rover_id': rover_id,
            'serial': serial
        }
        
        # Convert dict to JSON string
        message_body = json.dumps(message)
        
        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key=DEMINE_QUEUE,
            body=message_body
        )
        
        print(f"Published demine task for rover {rover_id} at {coordinates}")
        connection.close()
        
    except Exception as e:
        print(f"Error publishing demine task: {e}")

def publish_defused_mine(coordinates, rover_id, serial, pin):
    """Publishes a defused mine message to the Defused-Mines channel"""
    try:
        connection = get_connection()
        channel = connection.channel()
        
        # Declare the exchange (creates if doesn't exist)
        channel.exchange_declare(exchange=DEFUSED_MINES, exchange_type='fanout')
        
        # Create message payload
        message = {
            'coordinates': coordinates,
            'rover_id': rover_id,
            'serial': serial,
            'pin': pin
        }
        
        # Convert dict to JSON string
        message_body = json.dumps(message)
        
        # Publish message
        channel.basic_publish(
            exchange=DEFUSED_MINES,
            routing_key='',
            body=message_body
        )
        
        print(f"Published defused mine info for rover {rover_id} at {coordinates} with PIN {pin}")
        connection.close()
        
    except Exception as e:
        print(f"Error publishing defused mine: {e}")

def subscribe_to_demine_queue(callback):
    """Subscribes to the Demine-Queue channel"""
    try:
        connection = get_connection()
        channel = connection.channel()
        
        # Declare the queue (creates if doesn't exist)
        channel.queue_declare(queue=DEMINE_QUEUE)
        
        # Set up the callback
        channel.basic_consume(
            queue=DEMINE_QUEUE,
            on_message_callback=callback,
            auto_ack=True
        )
        
        print('Waiting for demine tasks. To exit press CTRL+C')
        channel.start_consuming()
        
    except Exception as e:
        print(f"Error subscribing to demine queue: {e}")

def subscribe_to_defused_mines(callback):
    """Subscribes to the Defused-Mines channel"""
    try:
        connection = get_connection()
        channel = connection.channel()
        
        # Declare the exchange
        channel.exchange_declare(exchange=DEFUSED_MINES, exchange_type='fanout')
        
        # Create a temporary queue with a random name
        result = channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        
        # Bind the queue to the exchange
        channel.queue_bind(exchange=DEFUSED_MINES, queue=queue_name)
        
        # Set up the callback
        channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True
        )
        
        print('Waiting for defused mine notifications. To exit press CTRL+C')
        channel.start_consuming()
        
    except Exception as e:
        print(f"Error subscribing to defused mines: {e}")