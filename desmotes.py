import sqlite3
import datetime
import calendar
import json
import sys
import subprocess, os

import argparse

parser = argparse.ArgumentParser(description='a simple tool for handling misfit shine data')
parser.add_argument('-v','--verbose', action="store_true", help='verbose output')
parser.add_argument('input', nargs='*', default=['Prometheus.sqlite'], help='shine databases')
parser.add_argument('-d','--database', default='desmotes.sqlite', help='export database')
parser.add_argument('-o','--output', default='desmotes.html', help='output HTML file')
parser.add_argument('-e','--export-only', action="store_true", help='just export, do not display')
# parser.add_argument('-p','--print', action="store_true", help='print to stdout')
# parser.add_argument('-t','--text-only', help='a pure text output')
args = parser.parse_args()

output_database = None
conn = None
c = None
dest_conn = sqlite3.connect(args.database)
d = dest_conn.cursor()

def create_db_structure():

    try:
        d.execute('SELECT * FROM graph')
        return
    except Exception as e:
        pass
        
    if args.verbose:
        print("creating new database {0} ...".format(args.database))

    # for table in ["graph", "movementevents", "weight"]:
    #     try:
    #         d.execute("DROP TABLE " + table)
    #     except Exception as e:
    #         if args.verbose:
    #             print("dropping table failed")

    d.execute('''
        CREATE TABLE movementevents (
            start DATE UNIQUE, 
            end DATE,
            synctime DATE, 
            distance INTEGER, 
            steps INTEGER,
            points INTEGER
        )
    ''')

    d.execute('''
        CREATE TABLE graph (
            timestamp DATE UNIQUE,
            synctime DATE, 
            value FLOAT
        )
    ''')

    d.execute('''
        CREATE TABLE weight (
            timestamp DATE UNIQUE,
            synctime DATE, 
            value FLOAT
        )
    ''')

    dest_conn.commit()
    # d.close()

def export():
    dublicate_count = 0

    for row in c.execute('SELECT ztimestamp, zupdatedat, zaveragevalue FROM zGraphItem ORDER BY ztimestamp ASC'):
        data = []
        data.append((int(row[0]), int(row[1]), float(row[2]))) 

        try:
            d.executemany("INSERT INTO graph VALUES (?, ?, ?)", data) # data = list of tuples
        except sqlite3.IntegrityError as e:
            dublicate_count += 1

    try:
        for row in c.execute('SELECT ztimestamp, zupdatedat, zprogressvalue FROM zWeightProgress ORDER BY ztimestamp ASC'):
            data = []
            data.append((int(row[0]), int(row[1]), float(row[2]) / 2.2046)) # lbs to kg
            
            try:
                d.executemany("INSERT INTO weight VALUES (?, ?, ?)", data) # data = list of tuples
            except sqlite3.IntegrityError as e:
                dublicate_count += 1
    except sqlite3.OperationalError as e:
        if args.verbose:
            print("[{0}] no weight data exported".format(output_database))

    for row in c.execute('SELECT ztimestamp, zupdatedat, zdata FROM zTimeLineItem WHERE zitemtype = 2 ORDER BY ztimestamp ASC'):
        data = []
        elem = json.loads(str(row[2]))
        data.append(( int(row[0]), int(row[0]) + elem["duration"], int(row[1]), elem["distance"], elem["steps"], elem["point"] ))

        try:
            d.executemany("INSERT INTO movementevents VALUES (?, ?, ?, ?, ?, ?)", data)
        except sqlite3.IntegrityError as e:
            dublicate_count += 1

    dest_conn.commit()

    if args.verbose:
        print("[{0}] dublicates omitted: {1}".format(output_database, dublicate_count))

def write_json():
    master = {}

    # GRAPH

    data = []
    for row in d.execute('SELECT * FROM graph ORDER BY timestamp ASC'):
        elem = {}
        elem["start"] = int(row[0]) * 1000
        elem["value"] = row[2]
        data.append(elem)

    master["graph"] = data

    # MINUTE

    minute_data = [0] * 1440 # 24 * 60
    for elem in data:
        time = datetime.datetime.fromtimestamp(elem["start"] / 1000)
        if elem["value"] > 0:
            minute_data[time.hour * 60 + time.minute] += elem["value"]

    max_value = max(minute_data)
    for i in range(0, len(minute_data)):
        if minute_data[i] > 0:
            minute_data[i] = minute_data[i] / max_value

    compr_data = [0] * 144 * 2
    for i in range(0, len(minute_data)):
        compr_data[i / 5] += minute_data[i]

    for i in range(0, len(compr_data)):
        compr_data[i] =  compr_data[i] / 5

    master["minute"] = compr_data

    # WEIGHT

    weight_data = []
    for row in d.execute('SELECT * FROM weight ORDER BY timestamp ASC'):
        elem = {}
        elem["timestamp"] = row[0] * 1000
        elem["value"] = row[2]
        weight_data.append(elem)

    master["weight"] = weight_data

    # DAY -> single

    min_day = datetime.datetime.fromtimestamp(data[0]["start"] / 1000)
    max_day = datetime.datetime.fromtimestamp(data[len(data)-1]["start"] / 1000)

    diff = max_day - min_day

    min_day = min_day - datetime.timedelta(hours = min_day.hour, minutes = min_day.minute, seconds = min_day.second)

    day_data = [0] * diff.days 
    for i in range(0, len(day_data)):
        start = min_day + datetime.timedelta(days=i)
        end = start + datetime.timedelta(days=1, seconds=-1)
        start = calendar.timegm(start.timetuple()) # convert to timestamp
        end = calendar.timegm(end.timetuple())
        sum = 0
        for elem in data:
            if elem["start"]/1000 >= start and elem["start"]/1000 < end:
                if elem["value"] > 0:
                    sum += elem["value"]

        day_data[i] = {}
        day_data[i]["timestamp"] = start*1000
        day_data[i]["value"] = sum

    master["day"] = day_data

    # DAY -> weekday

    # TODO


    f = open('data.json','w')
    f.write("var data = '")
    json_data = json.dumps(master)
    f.write(json_data)
    f.write("';")
    f.close()

if __name__ == "__main__":

    create_db_structure()

    for db in args.input:
        if not os.path.isfile(db):
            print("[{0}] does not exist".format(db))
            sys.exit(-1)

        output_database = db
        conn = sqlite3.connect(db)
        c = conn.cursor()
        export()

    if not args.export_only:
        write_json()

        # open output file
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', args.output))
        elif os.name == 'nt':
            os.startfile(output)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', output))



'''
zTimeLineItem.zItemType (timeline: squares)

0 /
1 /
2 single activity events
3 ?
4 timeline events (highscore, etc)
5 sleep
6 /
7 single movement events
    "duration"-value in sec


2:

{
  "steps" : 606,
  "distance" : 0.2607787,
  "rawPoint" : 151,
  "isBestRecord" : false,
  "calories" : 33.93726,
  "activityType" : 0,
  "typeChanges" : [

  ],
  "duration" : 480,
  "point" : 151
}

# 3:

{
  "milestoneType" : 1,
  "unitSystem" : 1
}

# 4:

{
  "eventType" : 5,
  "info" : {
    "exceededAmount" : 1082,
    "point" : 3326
  }
}

# 5:

{
  "realDeepSleepTimeInMinutes" : 141,
  "bookmarkTime" : 1392837993,
  "realEndTime" : 1392850833,
  "realStartTime" : 1392838053,
  "isFirstSleepOfDay" : true,
  "realSleepTimeInMinutes" : 197,
  "isAutoDetected" : true,
  "normalizedSleepQuality" : 52,
  "sleepStateChanges" : [
    [ 0, 2],
    [ 8, 3],
    [20, 2],
    [40, 3],
    [149, 2],
    [156, 1],
    [173, 2],
    [179, 3],
    [199, 2]
    ]
}

# 7:

{
  "duration" : 1020,
  "point" : 26,
  "calories" : 5.843503,
  "distance" : 0.04036666,
  "steps" : 102
}
'''