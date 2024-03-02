import pytest
import dateutil
from dateutil import parser
from datetime import timezone, timedelta
import json
from src.algo.dvr_algo import video_prep
from urllib.request import urlopen

def test_event_video():
    input_list_events = [] # to store all the events with .mp4 extension
    eventVideoCall = video_prep()
    eventVideoCall.db_details()

    start_time=eventVideoCall.start_time
    end_time=eventVideoCall.end_time
    vehicle_no=eventVideoCall.vehicle_no

    endpoint = "http://10.252.93.189:4000/api/v1/trips?"
    final_endpoint = endpoint + "vehicle=" + vehicle_no + \
                             "&start=" + start_time + "&end=" + end_time
    url = final_endpoint
    response = urlopen(url)
    tripData = json.loads(response.read())

    for i in range(tripData['trips'].__len__()):

        event_time = dateutil.parser.parse(tripData['trips'][i]['startTimeInISO']).replace(
            tzinfo=timezone.utc).astimezone(
            dateutil.tz.tzlocal())
        alertType = tripData['trips'][i]["alertType"]
        eventVideo =event_time.strftime("%H_%M_%S")+ "_" + str(alertType) + ".mp4"
        input_list_events.append(eventVideo)

    eventVideoCall.meta_details()
    eventVideoCall.video_stitch()
    generated_even_videos=[]
    generated_even_videos = eventVideoCall.event_vid
    input_list_events.sort()
    generated_even_videos.sort()

    assert set(input_list_events) >= set(generated_even_videos)

if __name__ == "__main__":
    pytest.main()


