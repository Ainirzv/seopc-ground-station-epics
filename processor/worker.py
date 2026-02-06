import json
import os
import time
import cv2
import numpy as np
from kafka import KafkaConsumer
from minio import Minio
import psycopg2
from io import BytesIO

# Configuration
KAFKA_BROKER = "127.0.0.1:19092"
TOPIC_NAME = "eo-events"
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "password123"
SOURCE_BUCKET = "satellite-raw"
DEST_BUCKET = "satellite-processed"
LOCAL_SYNC_PATH = "../local_sync/latest_processed.jpg"
PG_CONN_STR = "dbname=seopc_metadata user=admin password=password123 host=localhost port=5432"

def main():
    print("Starting Processing Worker...")
    
    # 1. Connect to MinIO
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    if not minio_client.bucket_exists(DEST_BUCKET):
        try:
            minio_client.make_bucket(DEST_BUCKET)
            print(f"Created bucket: {DEST_BUCKET}")
        except Exception:
            pass # Bucket might exist

    # 2. Connect to Postgres
    try:
        conn = psycopg2.connect(PG_CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        # Ensure table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processing_logs (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                processed_at TIMESTAMPTZ DEFAULT NOW(),
                latency_ms INTEGER
            );
        """)
        print("Connected to Postgres and ensured table exists.")
    except Exception as e:
        print(f"Postgres connection failed: {e}")
        return

    # 3. Connect to Kafka (with retry)
    consumer = None
    retries = 30
    while retries > 0:
        try:
            print(f"Connecting to Kafka at {KAFKA_BROKER}...")
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=[KAFKA_BROKER],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print(f"Connected to Kafka! Listening on {TOPIC_NAME}...")
            break
        except Exception as e:
            print(f"Kafka connection failed: {e}. Retrying in 2s... ({retries} left)")
            time.sleep(2)
            retries -= 1
    
    if not consumer:
        print("Could not connect to Kafka after multiple attempts.")
        return

    os.makedirs(os.path.dirname(LOCAL_SYNC_PATH), exist_ok=True)

    for message in consumer:
        try:
            start_time = time.time()
            data = message.value
            filename = data.get("file")
            print(f"Received event for file: {filename}")

            # Download from MinIO
            response = minio_client.get_object(SOURCE_BUCKET, filename)
            file_data = response.read()
            response.close()
            response.release_conn()

            # Process Image (Edge Detection)
            nparr = np.frombuffer(file_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                print(f"Failed to decode image {filename}")
                continue

            edges = cv2.Canny(img, 100, 200)

            # Encode back to jpg
            _, buffer = cv2.imencode('.jpg', edges)
            processed_data = BytesIO(buffer)

            # Upload to MinIO
            minio_client.put_object(
                DEST_BUCKET,
                filename,
                processed_data,
                len(buffer),
                content_type="image/jpeg"
            )
            print(f"Uploaded processed {filename}")

            # Save Locally for GUI
            with open(LOCAL_SYNC_PATH, "wb") as f:
                f.write(buffer)
            print(f"Updated local sync copy")

            # Log to Postgres
            latency = int((time.time() - start_time) * 1000)
            cur.execute(
                "INSERT INTO processing_logs (filename, latency_ms) VALUES (%s, %s)",
                (filename, latency)
            )
            print(f"Logged to DB. Latency: {latency}ms")

        except Exception as e:
            print(f"Error processing message: {e}")

if __name__ == "__main__":
    main()
