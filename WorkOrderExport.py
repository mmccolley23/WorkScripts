##Import libraries
import requests, json
import datetime
import time
from arcgis.gis import GIS
from dateutil import tz
from arcgis.apps import workforce

##Grab token to nycgov org
gis = GIS("https://yourorg.maps.arcgis.com/", "username", "password")
token = gis._con.token
#print(token)


##Search and return the CPR layer
item = gis.content.get("itemid")
##project = workforce.Project(item)
##project


##Identify type
#print(type(item))

##Search and return the WorkOrders layer
WorkOrders = (gis.content.get("itemid"))


#Define and pull in the url for the CPR feature layer
cpr_layers = item.layers
cpr_layer = cpr_layers[0]

##Query the CPR feature layer
cpr_df = cpr_layer.query().sdf
cpr_df.head(5)

#Define and pull in the url for the WorkOrders feature layer
wo_layers = WorkOrders.layers
wo_layer = wo_layers[0]


#Get the REST endpoint properties
properties = wo_layer.properties
#print(properties)


##Query the CPR feature layer
wo_df = wo_layer.query().sdf


#print('Converting the feature layers to spatial data frames..')

##Look for new entries made within the last XX minutes (or days)
# Establish timezone values for converting values
from_zone = tz.gettz('America/New_York')
to_zone = tz.gettz('UTC')

# Process timezone information
# Set current datetime to EST, then transform that value to UTC and convert to epoch
initial_datetime = datetime.datetime.now()
one_minute = datetime.timedelta(minutes=30)
final_datetime = initial_datetime - one_minute

eastern = final_datetime.replace(tzinfo=from_zone)
utc_value = eastern.astimezone(to_zone)
utc_timestamp = time.mktime(utc_value.timetuple())

timestamp_final = int(str(int(utc_timestamp)) + '000')

#print('Converting timestamp to UTC..')

queryDate = utc_value.strftime("%Y-%m-%d %H:%M:%S")


query = "EditDate > TimeSTAMP '" + queryDate + "'"
# query = "EditDate > TimeSTAMP '2022-02-07 09:16:43'"
#print(query)
# query = "1=1"

query_result = wo_layer.query(where=query, out_fields='*')
#print(len(query_result.features))
#print('Querying based on timestamp difference..')

#Alexs version
#Create a final features list (list of jsons that are manipulated and thrown into a final list
final_features = []
# # type(query_result.features)

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


#print('Looping through the updates from Workforce to CPR..')

for row in query_result.features:
    # print(row.attributes)
    #     print(type(row.attributes))
    #     print(row.geometry)

    test = row.as_dict
    # We need to pull attributes and relevant geometry into the new work order row in the work order feature service.
    attrib_dict = {}

    for k, v in test.items():
        if k == 'attributes':
            # You need to look at assignmenttype filters first, then jump into the next loop
            testvalue = v['assignmenttype']
            attrib_dict['resolutiondt'] = v['completeddate']
            temp_status = v['status']  # status 1 is assigned

            # Establish query to original CPR layer to pull out objectid
            #print(v['workorderid'])
            attrib_dict['probid'] = v['workorderid']
            query1 = '"probid" = ' + "'" + str(attrib_dict['probid']) + "'"
            #print(query1)
            wo_query_result = cpr_layer.query(query=query1)
            wo_dict = wo_query_result.to_dict()

            if v['completeddate'] is None:
                print('** COMPLETED DATE **: %s' % str(v['completeddate']))
                pass
            else:
                attrib_dict['resolutiondt'] = v['completeddate']

            # print(wo_dict)

            for key, value in wo_dict.items():
                # print(value)
                #print(key)
                if key == 'features':

                    for row in value:
                        if row['attributes'].get('probid') == str(attrib_dict['probid']):
                            print(row['attributes'].get('OBJECTID'))
                            objectid = row['attributes'].get('OBJECTID')
                            attrib_dict['OBJECTID'] = objectid

                    for row1 in properties['fields']:
                        if row1['name'] == 'status':
                            #print(row['domain']['codedValues'])
                            newrow = row1['domain']['codedValues']
                            for item in newrow:
                                if temp_status == item['code']:
                                    print(item['name'])
                                    attrib_dict['status'] = item['name']


            # Add additional status content here
            if testvalue == 'd41ff844-9ed5-42a1-92f7-b86a3cdd3354':
                attrib_dict['category'] = 'Road'
            elif testvalue == 'f7873e80-4b66-438c-8595-559685e0d4c4':
                attrib_dict['category'] = 'Animal'
            elif testvalue == 'fda9c402-bfb4-44e8-8375-ddb349dd1996':
                attrib_dict['category'] = 'Health'
            elif testvalue == '72cf7dc3-0ed0-44e4-81c8-055d72818771':
                attrib_dict['category'] = 'Blight'
            elif testvalue == '0b60c32a-03eb-4a4f-a8e0-928b94ffc6e6':
                attrib_dict['category'] = 'Trash'
            elif testvalue == 'c29df738-1b2f-43bd-802f-d423807b9631':
                attrib_dict['category'] = 'Snow'
            #print(attrib_dict)
            #print('Updates to CPR layer succeeded.')


            print(attrib_dict)

            #
            # Convert dictionaries into a JSON String
            att = json.dumps(attrib_dict)



            # Manipulate the string to reconstruct proper JSON
            att.lstrip('{')
            att = '{"attributes":' + att + '}'


            # Add the two json strings together, convert back to diciontary and load into list to prepare for data insert into
            # service.

            data_dict = json.loads(att)

            final_features.append(data_dict)
            print(final_features)

            # KEEP THIS COMMENTED OUT UNTIL YOU ARE READY TO PUSH INTO WORKFORCE
            edit_job = cpr_layer.edit_features(updates=final_features, rollback_on_failure=True)
            print(edit_job)

            # Reset aggregated JSON list and python dictionaries for next loop
            final_features = []
            attrib_dict = {}


