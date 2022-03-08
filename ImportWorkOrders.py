##Import libraries
import requests
import json
import time
import datetime
from dateutil import tz
from arcgis.gis import GIS
from arcgis.apps import workforce

def importwo(gisconn):
    # Authenticate with ArcGIS Online
    gis = gisconn

    # Search and return the CPR layer
    item = gis.content.get("itemid")

    # Search and return the WorkOrders layer
    WorkOrders = (gis.content.get("itemid"))

    # Define and pull in the url for the CPR feature layer
    cpr_layers = item.layers
    cpr_layer = cpr_layers[0]

    # Define and comment table associated with the CPR layer
    cpr_tables = item.tables
    cpr_comments = cpr_tables[0]

    # Define and pull in the url for the WorkOrders feature layer
    wo_layers = WorkOrders.layers
    wo_layer = wo_layers[0]


    # Establish timezone values for converting values
    from_zone = tz.gettz('America/New_York')
    to_zone = tz.gettz('UTC')

    # Look for new entries made within the last XX minutes (or days)
    initial_datetime = datetime.datetime.now()

    # Time DIFF SET TO 30 minutes
    time_diff = datetime.timedelta(minutes=30)
    final_datetime = initial_datetime - time_diff

    report = initial_datetime.replace(tzinfo=from_zone)
    eastern = final_datetime.replace(tzinfo=from_zone)
    utc_value = eastern.astimezone(to_zone)
    utc_timestamp = time.mktime(utc_value.timetuple())

    # If wanting to add timestamp into the feature service, this is the value type for the json dictionary
    # timestamp_final = int(str(int(utc_timestamp)) + '000')

    # Establish string versions of the
    reportDate = report.strftime("%Y-%m-%d %H:%M:%S")
    queryDate = utc_value.strftime("%Y-%m-%d %H:%M:%S")

    query = "CreationDate > TimeSTAMP '" + queryDate + "'"
    print(query)
    # query = "1=1"
    query_result = cpr_layer.query(where=query, out_fields='*')
    print(len(query_result.features))

    # Create a final features list (list of jsons that are manipulated and thrown into a final list
    final_features = []
    comment_records = []
    cpr_status_updates = []

    # Need a lookup table for global ids for each worker
    Mary = "85ff7e0a-5e12-4681-9e52-8d78d670bb34"
    Alex = "c76312ec-02ef-456e-b2f4-f9c8c14ca3ff"

    # Need a lookup table for global ids for each assignment type
    Animal_Inspection = "f7873e80-4b66-438c-8595-559685e0d4c4"
    Blight_Inspection = "72cf7dc3-0ed0-44e4-81c8-055d72818771"
    Road_Inspection = "d41ff844-9ed5-42a1-92f7-b86a3cdd3354"
    Trash_Inspection = "0b60c32a-03eb-4a4f-a8e0-928b94ffc6e6"
    Snow_Inspection = "c29df738-1b2f-43bd-802f-d423807b9631"
    Health_Inspection = "fda9c402-bfb4-44e8-8375-ddb349dd1996"


    for row in query_result.features:

        test = row.as_dict
        # We need to pull attributes and relevant geometry into the new work order row in the work order feature service.
        attrib_dict = {}
        geom_dict = {}
        comment_dict = {}
        status_dict = {}
        for k, v in test.items():
            if k == 'geometry':
                geom_dict = v
            elif k == 'attributes':
                status_dict['GlobalID'] = v['GlobalID']
                status_dict['status'] = 'Received'
                status_dict['OBJECTID'] = v['OBJECTID']

                comment_dict['probguid'] = v['GlobalID']
                comment_dict['comments'] = 'Added to workforce.'
                comment_dict['pocfullname'] = 'Central IT'
                comment_dict['pocphone'] = 'Call GIS'
                comment_dict['pocemail'] = 'it@org.email'
                comment_dict['publicview'] = 'No'

                # You need to look at category filteres first, then jump into the next loop
                category_value = v['category']
                attrib_dict['notes'] = 'Added from Citizen Problem Reporter on: %s' % str(reportDate)
                attrib_dict['workorderid'] = v['probid']
                attrib_dict['location'] = v['locdesc']

                if category_value == 'Blight':
                    #print('Blight')
                    attrib_dict['description'] = 'Blight Problem Reported'
                    attrib_dict['status'] = '1' # status 1 is assigned
                    attrib_dict['priority'] = '1' # priority 1 is low
                    attrib_dict['assignmenttype'] = '{' + str(Blight_Inspection) + '}'  # hard coded to lookups
                    attrib_dict['workerid'] = '{' + str(Alex) + '}'  # hard coded to lookups
                elif category_value == 'Animal':
                    #print('Animal')
                    attrib_dict['description'] = 'Animal Problem Reported'
                    attrib_dict['status'] = '1' # status 1 is assigned
                    attrib_dict['priority'] = '1' # priority 1 is low
                    attrib_dict['assignmenttype'] = '{' + str(Animal_Inspection) + '}'  # hard coded to lookups
                    attrib_dict['workerid'] = '{' + str(Alex) + '}'  # hard coded to lookups
                elif category_value == 'Trash':
                    #print('Trash')
                    attrib_dict['description'] = 'Trash Problem Reported'
                    attrib_dict['status'] = '1' # status 1 is assigned
                    attrib_dict['priority'] = '1' # priority 1 is low
                    attrib_dict['assignmenttype'] = '{' + str(Trash_Inspection) + '}'  # hard coded to lookups
                    attrib_dict['workerid'] = '{' + str(Alex) + '}'  # hard coded to lookups
                elif category_value == 'Road':
                    #print('Road')
                    attrib_dict['description'] = 'Road Problem Reported'
                    attrib_dict['status'] = '1' # status 1 is assigned
                    attrib_dict['priority'] = '2' # priority 1 is low
                    attrib_dict['assignmenttype'] = '{' + str(Road_Inspection) + '}'  # hard coded to lookups
                    attrib_dict['workerid'] = '{' + str(Mary) + '}'  # hard coded to lookups
                elif category_value == 'Snow/Ice':
                    #print('Snow')
                    attrib_dict['description'] = 'Snow/Ice Problem Reported'
                    attrib_dict['status'] = '1' # status 1 is assigned
                    attrib_dict['priority'] = '2' # priority 1 is low
                    attrib_dict['assignmenttype'] = '{' + str(Snow_Inspection) + '}'  # hard coded to lookups
                    attrib_dict['workerid'] = '{' + str(Mary) + '}'  # hard coded to lookups
                elif category_value == 'Health':
                    #print('Health')
                    attrib_dict['description'] = 'Health Problem Reported'
                    attrib_dict['status'] = '1' # status 1 is assigned
                    attrib_dict['priority'] = '2' # priority 1 is low
                    attrib_dict['assignmenttype'] = '{' + str(Health_Inspection) + '}'  # hard coded to lookups
                    attrib_dict['workerid'] = '{' + str(Mary) + '}'  # hard coded to lookups
                ##If Abington wants to leave one unassigned, set status to 0 and remove the workerid line

                # Convert dictionaries into a JSON String
                att = json.dumps(attrib_dict)
                geo = json.dumps(geom_dict)
                comment = json.dumps(comment_dict)
                status = json.dumps(status_dict)


                # Manipulate the string to reconstruct proper JSON
                att.lstrip('{')
                att = '{"attributes":' + att
                geo.lstrip('{')
                geo = ',"geometry": ' + geo + '}'
                comment.lstrip('{')
                comment = '{"attributes":' + comment + '}'
                status.lstrip('{')
                status = '{"attributes":' + status + '}'

                # Add the two json strings together, convert back to diciontary and load into list to prepare for data insert into
                # service.
                concat = att + geo
                #print(concat)
                data_dict = json.loads(concat)
                comment_add = json.loads(comment)
                status_update = json.loads(status)

                final_features.append(data_dict)
                comment_records.append(comment_add)
                cpr_status_updates.append(status_update)

                # Add CPR records into workforce
                wo_add_job = wo_layer.edit_features(adds=final_features, rollback_on_failure=True)
                print('Adding to workforce...')
                print(wo_add_job)

                # Update CPR record to received
                cpr_update_job = cpr_layer.edit_features(updates=cpr_status_updates, rollback_on_failure=True)
                print('Updating CPR to received...')
                print(cpr_update_job)

                # Add comment into CPR comments indicating it was pushed to workforce
                wo_comment_job = cpr_comments.edit_features(adds=comment_records, rollback_on_failure=True)
                print('Add comment to record that has been pushed to workforce...')
                print(wo_comment_job)

                # Reset aggregated JSON list and python dictionaries for next loop
                final_features = []
                comment_records = []
                cpr_status_updates = []
                attrib_dict = {}
                geom_dict = {}
                comment_dict = {}


if __name__ == "__main__":
    importwo()
