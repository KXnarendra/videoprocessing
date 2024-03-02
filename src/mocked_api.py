import flask
import json
import time
import boto3
from flask import request, jsonify
import dateutil.parser
from datetime import timezone, timedelta
import config


app = flask.Flask(__name__)
app.config["DEBUG"] = True
client = boto3.client('s3',
                      aws_access_key_id='temp',
                      aws_secret_access_key='temp',
                      region_name='us-east-1',
                      endpoint_url='http://localhost:4566'
                      )
client1 = boto3.resource('s3',
                         aws_access_key_id='temp',
                         aws_secret_access_key='temp',
                         region_name='us-east-1',
                         endpoint_url='http://localhost:4566'
                         )

with open("../config/all_trip.json", encoding="utf8") as f:
    data_json = json.load(f)


@app.route('/', methods=['GET'])
def home():
    return "<h1>This is an API for trip details</h1><p> This site is a prototype API for Trip details</p>"


@app.route('/api/v1/trips/all', methods=['GET'])
def api_all():
    return jsonify(data_json)


@app.route('/api/v1/trips', methods=['GET'])
def trip():
    trip_no = []
    final = []
    eventList = {}

    if 'vehicle' in request.args and 'start' in request.args and 'end' in request.args:
        vehicle = request.args['vehicle']
        start = request.args['start']
        end = request.args['end']

    else:
        return "Error : No plate no provided. Please specify an Vehicle no."
    total = len((data_json['trips']))

    for i in range(total):
        v = data_json['trips'][i]['vehicle']['plateNo']
        if v == vehicle:
            if (data_json['trips'][i]['startTimeInISO']) != None and (data_json['trips'][i]['endTimeInISO']) != None:
                var1 = data_json['trips'][i]['startTimeInISO']
                var2 = data_json['trips'][i]['endTimeInISO']

                temp_s = time.strptime(start, '%Y-%m-%d')
                temp_e = time.strptime(end, '%Y-%m-%d')

                d1 = time.strptime((dateutil.parser.parse(var1).replace(
                    tzinfo=timezone.utc).astimezone(
                    dateutil.tz.tzlocal()).strftime('%Y-%m-%d')), '%Y-%m-%d')
                d2 = time.strptime((dateutil.parser.parse(var2).replace(
                    tzinfo=timezone.utc).astimezone(
                    dateutil.tz.tzlocal()).strftime('%Y-%m-%d')), '%Y-%m-%d')

                if temp_s <= d1 <= d2 <= temp_e:
                    trip_no.append(i)

    for j in range(len(trip_no)):
        var = trip_no[j]
        events_len = data_json['trips'][var]['casAlerts'].__len__()
        for m in range(events_len):
            final.append({"startTimeInISO": data_json['trips'][var]['casAlerts'][m]['startTimeInISO'],
                          "alertType": data_json['trips'][var]['casAlerts'][m]['alertType']})

    eventList['trips'] = final
    return (eventList)


@app.route('/api/v1/trips', methods=['POST'])
def process_json():
    processed = []
    final = {}
    file_url = []
    content_type = request.headers.get('Content-Type')
    if (content_type == 'application/json'):
        # json = request.json
        if 'vehicle' in request.args and 'start' in request.args and 'end' in request.args and 'cid' in request.args and 'id' in request.args:
            vehicle = request.args['vehicle']
            start = request.args['start']
            end = request.args['end']
            cid = request.args['cid']
            id = request.args['id']
            tl = len(data_json['trips'])
            for i in range(tl):
                print(i)
                if data_json['trips'][i]['_id'] == id:
                    print(data_json['trips'][i]['casAlerts'][0]['externalAlertId'])
                    if data_json['trips'][i]['casAlerts'][0]['externalAlertId'] != None:
                        bucket = client1.Bucket("sm-aps1-dvr-incoming-vid-dev")
                        totalCount = 0  # count
                        folder_name = "customer-" + cid + "/" + vehicle + "-" + start + "-" + end + "-" + "processed"
                        # for key in bucket.objects.all():
                        # for key in  bucket.list(prefix=folder_name):
                        for object_summary in bucket.objects.filter(Prefix=folder_name):
                            print(object_summary.key)
                            file_url_vid = '%s/%s/%s' % (
                                client.meta.endpoint_url, "sm-aps1-dvr-incoming-vid-dev", object_summary.key)
                            file_url.append(file_url_vid)
                            # size += key.size
                            totalCount += 1
                        # 'http://localhost:4566/sm-aps1-dvr-incoming-vid-dev/customer1/KA51ME7196-2021-07-14-2021-07-14-processed-17_10_51_me_ufcw.mp4
                        len_alerts = len(data_json['trips'][i]['casAlerts'])
                        for j in range(len_alerts):
                            print(j)
                            temp = data_json['trips'][i]['casAlerts'][j]['startTimeInISO']
                            dd1 = dateutil.parser.parse(temp).replace(
                                tzinfo=timezone.utc).astimezone(
                                dateutil.tz.tzlocal())
                            dd1 = dd1.strftime(
                                "%H_%M_%S")

                            eventType = data_json['trips'][i]['casAlerts'][j]['alertType']
                            path = str(dd1) + "_" + eventType + ".mp4"
                            finalPath = folder_name + "-" + path
                            for obj in bucket.objects.filter(Prefix=folder_name):
                                o_p, o_p1 = (obj.key).split('/', 1)
                                output = o_p + "/" + o_p1
                                if finalPath == output:
                                    data_json['trips'][i]['casAlerts'][j]['videoPath'] = file_url[j]

                        processed.append(data_json['trips'][i])
                        final['trips'] = processed

                        break

        return final
    else:
        return 'Content-Type not supported!'


app.run(host='0.0.0.0', port=4000, debug=True)
