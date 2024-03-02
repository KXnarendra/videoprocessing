import json
import os
import pika
from src.algo import dvr_algo


def start_video_editing(body):
    video_details = dvr_algo.video_prep()
    video_details.db_details(body)  # query form details from db
    video_details.download_all(body)  # download videos from s3 bucket for processing
    video_details.meta_details()  # get the meta-data details of the video
    video_details.video_stitch()  # video event stitch
    # video_details.combined_video()  # generate the combined video


if __name__ == '__main__':
    print("Start Localstack services via docker image and fire up S3 at port 4566")
    print("Start rabbitmq service on relevant port")
    amqp_url = os.environ['AMQP_URL']
    url_params = pika.URLParameters(amqp_url)
    connection = pika.BlockingConnection(url_params)
    channel = connection.channel()

    channel.queue_declare(queue='to_processing')
    print(' to_processing queue is  [*] Waiting for messages.')


    def callback(ch, method, properties, body):
        body = json.loads(body)
        print(" [x] Received %s" % body)  # queue receiving message after uploading to s3 finished
        start_video_editing(body)  # begin the video stitching activities
        print("Video processing is done and event videos url are uploaded into s3 bucket")
        print("Video url path POST to API")
        print(" [x] Done")
        # ch.basic_ack(delivery_tag=method.delivery_tag)


    # channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='to_processing',
                          on_message_callback=callback, auto_ack=True)
    channel.start_consuming()
    connection.close()
