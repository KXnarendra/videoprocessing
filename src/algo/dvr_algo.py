import copy
import glob
import json
import boto3, botocore
import cv2
import dateutil
import ffmpeg
import time
import numpy as np
from datetime import timezone, timedelta
from boto3.dynamodb.conditions import Key
from dateutil import parser
from moviepy.editor import *
from moviepy.editor import VideoFileClip
from moviepy.video.io.ffmpeg_writer import ffmpeg_write_video
from config import config
from urllib.request import urlopen

client = boto3.client('s3',
                      aws_access_key_id='temp',
                      aws_secret_access_key='temp',
                      region_name='us-west-2',
                      endpoint_url='http://host.docker.internal:4566'
                      )
client1 = boto3.resource('s3',
                         aws_access_key_id='temp',
                         aws_secret_access_key='temp',
                         region_name='us-west-2',
                         endpoint_url='http://host.docker.internal:4566'
                         )


class video_prep:

    def __init__(self):

        self.event_vid = []  # To maintain the list for all the event videos
        self.list_video_files = []  # ISO T-Z format video files from meta data ( creation time)
        self.list_video_files_date_time = []  # list of video files in datetime format
        self.file_dur = {}  # duration for video file name and duration mapped, assuming if each video is not 180 secs
        self.dic1 = {}  # dict maintained to map meta-data creation time vs actual raw video file name( dir contains raw video)
        self.creation_time = []  # taken to store the creation time for all video files ,
        self.event_times = []  # list to store all the event times from trip json
        self.timeDrift = None  # drift time being extracted from table

    def db_details(self, body):
        dynamodb = boto3.resource('dynamodb', aws_access_key_id='temp',
                                  aws_secret_access_key='temp',
                                  region_name='us-west-2',
                                  endpoint_url='http://host.docker.internal:4566')
        table = dynamodb.Table('Trip')
        query_customer_ID = str(body['query_param'])
        print(query_customer_ID)
        response = table.query(
            KeyConditionExpression=Key('customer_ID').eq(query_customer_ID)
        )
        items = response['Items']
        self.customerid = str(items[0]['customer_ID'])
        self.timeDrift = str(items[0]['vehicle_info']['Cam_lag'])
        self.start_time = str(items[0]['vehicle_info']['start_time'])
        self.end_time = str(items[0]['vehicle_info']['end_time'])
        self.vehicle_no = str(items[0]['vehicle_no'])
        print("Fetched db details")

    def download_all(self, body):

        video_prep.db_details(self, body)
        self.folder_name = "customer-" + self.customerid + "/" + \
                           self.vehicle_no + "-" + self.start_time + "-" + self.end_time
        bucket_name = "sm-aps1-dvr-incoming-vid-dev"
        print("reached download")
        try:
            client1.meta.client.head_bucket(Bucket=bucket_name)
            print("Bucket Exists!")

        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response['Error']['Code'])
            if error_code == 403:
                print("Private Bucket. Forbidden Access!")
                return True
            elif error_code == 404:
                print("Bucket Does Not Exist!")
                return False

        if not self.folder_name.endswith('/'):
            path = self.folder_name + '/'
        resp = client.list_objects(Bucket=bucket_name, Prefix=self.folder_name, Delimiter='/', MaxKeys=1)
        # return 'Contents' in resp
        bucket = client1.Bucket("sm-aps1-dvr-incoming-vid-dev")
        # for key in bucket.objects.all():
        for obj in bucket.objects.filter(Prefix=self.folder_name):
            o_p, o_p1, o_p2 = (obj.key).split('/', 2)
            print(o_p2)
            bucket.download_file(
                obj.key, (os.path.join(config.vid_path1, o_p2)))
        print("Downloaded all s3 videos from s3 bucket")

    def meta_details(self):
        """method to extract the meta-data details
            of the Raw video.

            Extract creation time , subtract with duration for start time
            Map meta-data vs Raw videos

           """
        # self.videoFiles = [os.path.basename(x) for x in glob.glob(
        #     os.path.join(config.vid_path1, "2021*.[mM][pP]4"))]
        self.videoFiles = [os.path.basename(x) for x in glob.glob(
            os.path.join(config.vid_path1, "2021*.[mM][pP]4"))]
        print(self.videoFiles)
        for file in self.videoFiles:
            value = (ffmpeg.probe(os.path.join(
                config.vid_path1, file))["streams"])
            self.duration1 = value[0]['duration']
            # creation video time is next video
            self.next_video_time = value[0]['tags']['creation_time']
            self.creation_time.append(self.next_video_time)
            next_video_time_datetime_format = dateutil.parser.parse(self.next_video_time).replace(
                tzinfo=timezone.utc).astimezone(
                dateutil.tz.tzlocal()) - (timedelta(minutes=330))

            self.curr_vid_time = next_video_time_datetime_format - timedelta(
                seconds=float(self.duration1))  # 180 secs subtract to get start time of video(creation time-duration)
            self.curr_vid_tim_tz = self.curr_vid_time.strftime(
                "%Y-%m-%dT%H:%M:%SZ")  # change the format
            self.file_dur[file] = self.duration1

            self.list_video_files.append(self.curr_vid_tim_tz)  # T-Z format
            self.list_video_files_date_time.append(
                self.curr_vid_time)  # datetime format
            self.list_video_files.sort()
            self.list_video_files_date_time.sort()

            for i in range(len(self.list_video_files)):
                self.dic1[self.list_video_files[i]] = self.videoFiles[i]

        print("Meta-data operation finished")

    def video_stitch(self):

        print("Drift time:", self.timeDrift)
        endpoint = "http://192.168.1.55:4000/api/v1/trips?"

        final_endpoint = endpoint + "vehicle=" + self.vehicle_no + \
                         "&start=" + self.start_time + "&end=" + self.end_time
        url = final_endpoint
        response = urlopen(url)
        tripData = json.loads(response.read())
        time.sleep(6)
        total_events = tripData['trips'].__len__()
        print("reached1")
        for k in range(total_events):

            event_logged = tripData['trips'][k]['startTimeInISO']
            print(event_logged)
            datetime_format_event_logged = dateutil.parser.parse(event_logged).replace(
                tzinfo=timezone.utc).astimezone(
                dateutil.tz.tzlocal()) + (timedelta(seconds=float(self.timeDrift)))  # event time
            datetime_format_event_start = datetime_format_event_logged - (timedelta(seconds=float(10)))
            print(datetime_format_event_start)
            datetime_format_event_end = datetime_format_event_logged + (timedelta(seconds=10))
            print(datetime_format_event_end)

            T_Z_format_event_start = datetime_format_event_start.strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            T_Z_format_event_end = datetime_format_event_end.strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            event_alert = tripData['trips'][k]['alertType']
            print(event_alert)
            start = end = 0
            bool = False
            total_videos = len(self.videoFiles)
            for i in range(total_videos):

                if self.list_video_files[i] <= T_Z_format_event_start:  # check for the correct video w.r.t. concatenation
                    start = i
                    bool = True

                if self.list_video_files[i] <= T_Z_format_event_end:
                    end = i
                else:
                    break  # if videos are not in range just jump to fetch new event
            if bool == False:
                continue
            combinedClipStartTime = self.list_video_files_date_time[start]
            combinedClipEndTime = self.list_video_files_date_time[end] + timedelta(
                seconds=float(self.file_dur[self.videoFiles[end]]))
            combinedClip = concatenate_videoclips([VideoFileClip(
                os.path.join(config.vid_path1, self.dic1[self.list_video_files[i]])) for i in range(start, end + 1)])
            eventVideosDir = "eventVideos"
            if not os.path.exists(os.path.join(config.vid_path1, eventVideosDir)):
                os.mkdir(os.path.join(config.vid_path1, eventVideosDir))
            videoPath = eventVideosDir + "/" + \
                        datetime_format_event_logged.strftime(
                            "%H_%M_%S") + "_" + str(event_alert) + ".mp4"  # constructing the event videopath
            clipDuration = 10
            eventTimeInVideo = (datetime_format_event_logged -
                                combinedClipStartTime).total_seconds()
            eventVideoStartTime = eventTimeInVideo - (clipDuration / 2)
            eventVideoEndTime = eventTimeInVideo + (clipDuration / 2)
            print("reached3")
            if (eventVideoStartTime < 0):
                eventVideoStartTime = 0

            if (eventVideoStartTime > combinedClip.duration):
                print("Video are missing or out of range g: greater than combinedclip duration ")
                continue

            def processFrame(getFrame, t):

                newFrame = copy.deepcopy(getFrame(t))
                (frameHeight, frameWidth, frameChannels) = newFrame.shape
                timelineBarRow = int(abs(frameHeight * 0.8))
                newFrame[timelineBarRow - 1:timelineBarRow + 1, :] = [0, 0, 0]  # full line
                col = int(
                    abs(np.interp(t, [eventVideoStartTime, eventVideoEndTime], [0, frameWidth])))
                colStart = col - 1
                colEnd = col + 1
                if colStart < 0:
                    colStart = 0
                if colEnd >= frameWidth:
                    colEnd = frameWidth - 1
                newFrame[timelineBarRow - 1:timelineBarRow +
                                            1, colStart:colEnd] = [255, 255, 255]
                eventCol = int(abs(np.interp(eventTimeInVideo, [
                    eventVideoStartTime, eventVideoEndTime], [0, frameWidth])))
                eventColStart = eventCol - 2
                eventColEnd = eventCol + 2
                if eventColStart < 0:
                    eventColStart = 0
                if eventColEnd >= 800:
                    eventColEnd = 800 - 1
                newFrame[timelineBarRow - 7:timelineBarRow + 7, eventColStart + 1:eventColEnd] = [255, 0,
                                                                                                  0]  # len of red bar above:below
                newFrame[timelineBarRow - 7:timelineBarRow + 7, eventColStart] = [0, 0,
                                                                                  0]  # left bar  #black bound around red bar
                newFrame[timelineBarRow - 7:timelineBarRow +
                                            7, eventColEnd] = [0, 0, 0]  # right bar
                newFrame[timelineBarRow - 7,
                eventColStart:eventColEnd] = [0, 0, 0]  # top bar
                newFrame[timelineBarRow + 7,
                eventColStart:eventColEnd] = [0, 0, 0]  # bottom bar
                st1 = (clipDuration / 2) - 2
                st2 = (clipDuration / 2) + 2

                # Warning text flashing from st to ft
                st = eventVideoStartTime + st1
                ft = eventVideoStartTime + st2

                # TO PUT FULL FORM FOR THE WARNINGS
                events1 = {
                    'me_fcw': 'Foward Collision Warning (FCW)',
                    'me_pcw': 'Pedestrian Collision Warning (PCW)',
                    'me_hmw': 'Headway Monitoring Warning (HMW)',
                    'me_lldw': 'Left Lane Departure Warning (LLDW)',
                    'me_rldw': 'Right Lane Departure Warning (RLDW)',
                    'speeding': 'Speeding',
                    'hard_brake': 'Hard Brake',
                    'me_twl': 'Traffic Warning Level (TWL)',
                    'over_acc': 'Harsh Accleration',
                    'me_ufcw': 'Forward Collision warning (FCW)',
                    'stoppage': 'Stoppage',
                    'none': 'No Event Named'
                }

                Text_to_put = events1.get(event_alert)

                # warning flashes for the time period mentioned under below condition
                # warning Flashy text put for the time period condition passed via cv2 putText
                if ((st < t < (st + 0.5)) or (st + 1 < t < (ft - 1.5)) or ((st + 2) < t < (ft - 0.4)) or (
                        st + 2.5 < t < (ft + 0.4))):
                    print("\n\n t value is : ", t)
                    cv2.putText(newFrame, Text_to_put, (eventCol - 55, timelineBarRow - 250),
                                cv2.FONT_HERSHEY_COMPLEX_SMALL,
                                0.8, (255, 0, 0), 1, cv2.LINE_AA,
                                bottomLeftOrigin=False)  # eventcol (-) neg incresese in  towards side left  , timeline  + below

                return newFrame

            combinedClip = combinedClip.fl(processFrame)
            timeInVideo = eventTimeInVideo - eventVideoStartTime
            eventVideo = combinedClip.subclip(
                eventVideoStartTime, eventVideoEndTime)
            eventVideo.duration = clipDuration
            num_of_non_zeros = np.count_nonzero(eventVideo.audio.clips[0].reader.buffer)

            if eventVideo.audio == None or (num_of_non_zeros) == 0:
                print("Mic off Videos")
                ffmpeg_write_video(eventVideo,
                                   os.path.join(config.vid_path1, videoPath),
                                   fps=combinedClip.fps,
                                   audiofile="/usr/src/app/consumer/consumer/edited.mp3",
                                   codec="h264", threads=4)
            else:
                print("MIC ON VIDEOS")
                eventVideo.write_videofile(os.path.join(config.vid_path1, videoPath),
                                           fps=combinedClip.fps,
                                           codec="h264", threads=4)
        eventVideosDir = "eventVideos"
        if not os.path.exists(os.path.join(config.vid_path1, eventVideosDir)):
            os.mkdir(os.path.join(config.vid_path1, eventVideosDir))
        for vid_file in os.listdir(os.path.join(config.vid_path1, eventVideosDir)):
            self.folder_name = "customer-" + self.customerid + "/" + self.vehicle_no + "-" + self.start_time + \
                               "-" + self.end_time + "-" + \
                               "processed-"

            if vid_file.endswith(".mp4"):
                self.event_vid.append(vid_file)
                client1.Bucket("sm-aps1-dvr-incoming-vid-dev").upload_file(
                    os.path.join(config.vid_path1, videoPath), self.folder_name + vid_file)
            print("Event video uploaded to s3")

    def combined_video(self):
        tripVideoPath = "combinedVideo.mp4"
        combinedVideoFile = os.path.join(config.vid_path1, tripVideoPath)
        events = []
        eventCount = 0
        videoFiles = [os.path.basename(x) for x in glob.glob(
            os.path.join(config.vid_path1, "2021*.[mM][pP]4"))]
        for e in self.event_times:
            if self.list_video_files[0] <= e < self.list_video_files[len(self.list_video_files) - 1]:
                eventTimeInVideo = (e - self.list_video_files_date_time[0]).total_seconds()
                events.append(eventTimeInVideo)
                # self.events[eventTimeInVideo] = e.eventType
            eventCount = eventCount + 1

        def processFrame(getFrame, t):

            newFrame = copy.deepcopy(getFrame(t))
            (frameHeight, frameWidth, frameChannels) = newFrame.shape
            timelineBarRow = int(abs(frameHeight * 0.8))
            newFrame[timelineBarRow - 1:timelineBarRow +
                                        1, :] = [0, 0, 0]  # full line
            col = int(
                abs(np.interp(t, [0, combinedClip.duration], [0, frameWidth])))
            colStart = col - 1
            colEnd = col + 1
            if colStart < 0:
                colStart = 0
            if colEnd >= frameWidth:
                colEnd = frameWidth - 1
            newFrame[timelineBarRow - 1:timelineBarRow +
                                        1, colStart:colEnd] = [255, 255, 255]
            for eventTimeInVideo in events:
                eventCol = int(
                    abs(np.interp(eventTimeInVideo + float(self.timeDrift), [0, combinedClip.duration],
                                  [0, frameWidth])))
                eventColStart = eventCol - 2
                eventColEnd = eventCol + 2
                if eventColStart < 0:
                    eventColStart = 0
                if eventColEnd >= 800:
                    eventColEnd = 800 - 1
                newFrame[timelineBarRow - 7:timelineBarRow + 7,
                eventColStart + 1:eventColEnd] = [255, 0, 0]
                newFrame[timelineBarRow - 7:timelineBarRow +
                                            7, eventColStart] = [0, 0, 0]  # left bar
                newFrame[timelineBarRow - 7:timelineBarRow +
                                            7, eventColEnd] = [0, 0, 0]  # right bar
                newFrame[timelineBarRow - 7,
                eventColStart:eventColEnd] = [0, 0, 0]  # top bar
                newFrame[timelineBarRow + 7,
                eventColStart:eventColEnd] = [0, 0, 0]  # bottom bar

        if not os.path.exists(combinedVideoFile):
            print("Loading all videos...")
            videoFiles.sort()
            videoClips = [VideoFileClip(os.path.join(
                config.vid_path1, i)) for i in videoFiles]
            print("Stitching all videos...")
            combinedClip = concatenate_videoclips(videoClips)

        else:
            print("Loading combined video from", combinedVideoFile)
            combinedClip = VideoFileClip(combinedVideoFile)
            combinedClip = combinedClip.fl(processFrame)

        if (combinedClip.audio) == None or combinedClip.audio.clips[0].reader.infos['audio_found'] == False:

            ffmpeg_write_video(combinedClip,
                               os.path.join(config.vid_path2, tripVideoPath),
                               fps=combinedClip.fps,
                               audiofile="C:\\workspace\\Python_proj\\dvr_audio1\\edited.mp3",
                               codec="h264", threads=4)
        else:
            print("MIC ON VIDEOS")
            combinedClip.write_videofile(os.path.join(config.vid_path1, tripVideoPath),
                                         fps=combinedClip.fps,
                                         codec="h264", threads=4)
        print("Combined video generated")
