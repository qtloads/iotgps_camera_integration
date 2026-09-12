import requests
import json
import time
from datetime import datetime
import db
import logging
from pymongo.errors import BulkWriteError

ALL_DATA = True
RECORD_WAIT = 1
BATCH_WAIT = 2
BATCH_SIZE = 3000

# API details
url = "https://vltd.qtloads.com/gps/rest/v4/tpr/vehicle/route/history"

# Bearer token
bearer_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJxdGxvYWRzIiwiZXhwIjoxNzk2NzI5OTMxLCJpYXQiOjE3NjUxOTM5MzF9.AN0wnriuTMlMV7AwTRyqC0Y1bZrxqoY2_rONAhrjr4U"

# Headers
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {bearer_token}"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

def get_data(payload):
    responseData = {}
    final_req = {}
    final_req["ouid"] = payload["ouid"]
    final_req["dateRange"] = payload["dateRange"]
    print("Vehicle Number: ", payload["vehicleNo"])
    print("Daterange: ", payload["dateRange"])
    try:
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(final_req)
        )
        print("Status Code:", response.status_code)
        print(f"Response Time :-----------------> {response.elapsed.total_seconds():.3f} seconds")
        responseData = response.json()
    except Exception as e:
        print("Error:", str(e))
        payload = []
    return responseData

def saveResponse(data, reqId):
    total_read = 0
    total_inserted = 0
    total_duplicates = 0
    overall_success = True

    for start in range(0, len(data), BATCH_SIZE):

        batch = data[start:start + BATCH_SIZE]
        total_read += len(batch)
        try:
            result = db.gpsTrack.insert_many(
                batch,
                ordered=False
            )

            inserted_count = len(result.inserted_ids)
            total_inserted += inserted_count
            logger.info(
                f"Processed: {total_read}/{len(data)} | "
                f"Inserted: {total_inserted}"
            )

            if inserted_count != len(batch):
                overall_success = False

        except BulkWriteError as e:

            overall_success = False

            inserted_count = e.details.get("nInserted", 0)
            total_inserted += inserted_count

            logger.error(
                f"Bulk insertion failed | "
                f"Batch: {start} - {start + len(batch)} | "
                f"Inserted: {inserted_count} | "
                f"Error: {e.details}"
            )

        except Exception as e:

            overall_success = False

            logger.error(
                f"Batch insertion failed | "
                f"Batch: {start} - {start + len(batch)} | "
                f"Error: {e}",
                exc_info=True
            )

    # Set final status only after ALL batches are processed
    db.requestCollection.update_one(
        {"_id": reqId},
        {"$set": 
            {
                "status": 1 if overall_success else 2, 
                "updatedAt" : datetime.now(),
                "total_inserted" : total_inserted,
                "total_data" : len(data)
            }
        }
    )
    print("Process End...")

def processRequest(veh_req):
    # print("processRequest ",veh_req)
    for req in veh_req:
        reqId = req["_id"]
        try:
            veh_data = get_data(req)
            stsCode =  veh_data.get("code")
            dataLen =  veh_data.get("data")
            print("Data Length", len(dataLen))
            if stsCode == 200 and len(dataLen) > 0:
                saveResponse(dataLen, reqId)
            else:
                print("Skip Track")
                db.requestCollection.update_one(
                    {"_id": reqId},
                    {"$set": 
                        {
                            "status": 2, 
                            "updatedAt" : datetime.now(),
                            "total_data" : len(dataLen),
                            "api_status" : stsCode
                        }
                    }
                )
        except Exception as err:
            print("Exception-3 : ",err)
            db.requestCollection.update_one(
                {"_id": reqId},
                {"$set": 
                    {
                        "status": 2, 
                        "updatedAt" : datetime.now()
                    }
                }
            )
        print(".................Sleeping...............!")
        time.sleep(RECORD_WAIT)

def get_request_list():
    try:
        veh_req = list(db.requestCollection.find({"status" : 0}).limit(50))
        if len(veh_req) == 0:
            ALL_DATA = False
        # print("get_request_list", veh_req)
        try:
            processRequest(veh_req)
        except Exception as err:
            print("Exception-2 : ",err)
    except Exception as err:
        print("Exception-1 : ",err)
        pass

def call_cronjob():
    while ALL_DATA:
        get_request_list()
        time.sleep(BATCH_WAIT)


# call_cronjob()