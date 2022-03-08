# ------------------------------------------------------------------------------
# Name:        calculateids.py
# Purpose:     generates identifiers for features

# Copyright 2017 Esri

#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# ------------------------------------------------------------------------------

# from send_email import EmailServer
import re
from datetime import datetime as dt
from os import path, sys
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
import json
import ImportWorkOrders

#id_settings = {}
#modlists = {}
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib, sys

COMMASPACE = ', '


def mailserver(smtp_server, uname, pword, tls_):
    server = smtplib.SMTP(smtp_server, 587)
    server.ehlo()
    if bool(tls_):
        server.starttls()
    else:
        pass
    server.login(uname, pword)
    return server


def sendemail(smtp, from_address, reply_to, to_addresses, subject, email_body):
    msg = MIMEText(email_body, 'html')
    msg['To'] = COMMASPACE.join(to_addresses)
    temp_to = COMMASPACE.join(to_addresses)
    temp_to.replace(" ","")
    final_receipients = temp_to.split(",")
    # msg['Cc'] = COMMASPACE.join(cc)
    msg['From'] = from_address
    msg['X-Priority'] = '2'
    msg['Subject'] = subject
    server = smtp
    server.sendmail(reply_to, final_receipients, msg.as_string())


def _add_warning(message):
    try:
        import arcpy
        arcpy.AddWarning(message)
    except ImportError:
        print(message)

def _set_result(index, value):
    try:
        import arcpy
        arcpy.SetParameter(index, value)
    except ImportError:
        pass

def _add_message(msg, ertype='ERROR'):
    print("{}: {}".format(ertype, msg))
    with open(path.join(sys.path[0], 'id_log.log'), 'a') as log:
        log.write("{} -- {}: {}".format(dt.now(), ertype, msg))
    return


def _report_failures(results):
    for result in results['updateResults']:
        if not result['success']:
            _add_message('{}: {}'.format(result['error']['code'], result['error']['description']))
    return


def _get_features(feature_layer, where_clause, return_geometry=False):
    """Get the features for the given feature layer of a feature service. Returns a list of json features.
    Keyword arguments:
    feature_layer - The feature layer to return the features for
    where_clause - The expression used in the query"""
    print(where_clause)
    total_features = []
    max_record_count = feature_layer.properties['maxRecordCount']
    if max_record_count < 1:
        max_record_count = 1000
    offset = 0
    if not where_clause:
        print('no where clause')
    while True:
        if not where_clause:
            where_clause = "1=1"
        print(where_clause)
        features = feature_layer.query(where=where_clause,
                                       return_geometry=return_geometry,
                                       result_offset=offset,
                                       result_record_count=max_record_count).features
        total_features += features
        if len(features) < max_record_count:
            break
        offset += len(features)
    return total_features


def add_identifiers(lyr, seq, fld):
    """Update features in an agol/portal service with id values
    Return next valid sequence value"""

    # Get features without id
    value = id_settings[seq]['next value']
    fmt = id_settings[seq]['pattern']
    interval = id_settings[seq]['interval']

    rows = _get_features(lyr, """({} is null) OR ({} = '') OR ({} = '<Null>') OR ({} = 'Null')""".format(fld, fld, fld, fld))

    # For each feature, update id, and increment sequence value
    for row in rows:
        row.attributes[fld] = fmt.format(value)
        value += interval
        if row.attributes['emailstatus'] == '<Null>':
            row.attributes['emailstatus'] = 'Null'
        print(row)

    if rows:
        results = lyr.edit_features(updates=rows)
        _report_failures(results)

    return value


def enrich_layer(source, target, settings):
    wkid = target.properties.extent.spatialReference.wkid

    # Query for target features
    rows = _get_features(target, "1=1", return_geometry=True)

    for row in rows:
        # Perform spatial query to get attributes of intersecting feature
        ptgeom = {'geometry': row.geometry,
                  'spatialRel': 'esriSpatialRelIntersects',
                  'geometryType': 'esriGeometryPoint',
                  'inSR': wkid
                  }
        sourcefeat = source.query(geometry_filter=ptgeom)

        try:
            # Only first feature is processed
            source_val = sourcefeat.features[0].attributes[settings['source']]
            row.attributes[settings['target']] = source_val
        except IndexError:
            continue  # no intersecting feature found

    if rows:
        results = target.edit_features(updates=rows)
        _report_failures(results)

    return


def build_expression(words, match_type, subs):
    """Build an all-caps regular expression for matching either exact or
    partial strings"""

    re_string = ''

    for word in words:
        new_word = ''
        for char in word.upper():

            # If listed, include substitution characters
            if char in subs.keys():
                new_word += "[" + char + subs[char] + "]"

            else:
                new_word += "[" + char + "]"

        # Filter using only exact matches of the string
        if match_type == 'EXACT':
            re_string += '\\b{}\\b|'.format(new_word)

        # Filter using all occurances of the letter combinations specified
        else:
            re_string += '.*{}.*|'.format(new_word)

    # Last character will always be | and must be dropped
    return re_string[:-1]


def moderate_features(lyr, settings):
    rows = _get_features(lyr, settings['sql'])
    for row in rows:
        for field in settings['scan fields'].split(';'):
            try:
                text = row.get_value(field)
                text = text.upper()
            except AttributeError:  # Handles empty fields
                continue

            if re.search(modlists[settings['list']], text):
                row.attributes[settings['field']] = settings['value']
                break

    if rows:
        results = lyr.edit_features(updates=rows)
        _report_failures(results)
    return


def _get_value(row, fields, sub):
    val = row.attributes[sub]

    if val is None:
        val = ''
    elif type(val) != str:
        for field in fields:
            if field['name'] == sub and 'Date' in field['type']:
                try:
                    val = dt.fromtimestamp(
                        row.attributes[sub]).strftime('%c')
                except OSError:  # timestamp in milliseconds
                    val = dt.fromtimestamp(
                        row.attributes[sub] / 1000).strftime('%c')
                break
        else:
            val = str(val)
    return val


def build_email(row, fields, settings):

    email_subject = ''
    email_body = ''

    if settings['recipient'] in row.fields:
        email = row.attributes[settings['recipient']]
    else:
        email = settings['recipient']

    try:
        html = path.join(path.dirname(__file__), settings['template'])
        with open(html) as file:
            email_body = file.read()
            email_subject = settings['subject']
            if substitutions:
                for sub in substitutions:
                    if sub[1] in row.fields:
                        val = _get_value(row, fields, sub[1])

                        email_body = email_body.replace(sub[0], val)
                        email_subject = email_subject.replace(sub[0], val)
                    else:
                        email_body = email_body.replace(sub[0], str(sub[1]))
                        email_subject = email_subject.replace(sub[0], str(sub[1]))
    except:
        _add_message('Failed to read email template {}'.format(html))

    return email, email_subject, email_body


def main(configuration_file):
    global gisconn
    try:
        with open(configuration_file) as configfile:
            cfg = json.load(configfile)

        #gis = GIS(cfg['organization url'], cfg['username'], cfg['password'])
        gis = GIS(cfg['https://nycgov.maps.arcgis.com/'], cfg['mmccolley_nycgov'], cfg['GIS4day$!'])
        print(gis)
        gisconn = gis

        # Get general id settings
        global id_settings
        id_settings = {}
        for option in cfg['id sequences']:
            id_settings[option['name']] = {'interval': int(option['interval']),
                                           'next value': int(option['next value']),
                                           'pattern': option['pattern']}

        # Get general moderation settings
        global modlists
        modlists = {}
        subs = cfg['moderation settings']['substitutions']
        for modlist in cfg['moderation settings']['lists']:
            words = [str(word).upper().strip() for word in modlist['words'].split(',')]
            modlists[modlist['filter name']] = build_expression(words, modlist['filter type'], subs)

        # Get general email settings
        server = cfg['email settings']['smtp server']
        username = cfg['email settings']['smtp username']
        password = cfg['email settings']['smtp password']
        tls = cfg['email settings']['use tls']
        from_address = cfg['email settings']['from address']
        if not from_address:
            from_address = ''
        reply_to = cfg['email settings']['reply to']
        if not reply_to:
            reply_to = ''
        global substitutions
        substitutions = cfg['email settings']['substitutions']

        # Process each service
        for service in cfg['services']:
            ##            print(service)
            ##            print(service['url'])
            try:
                lyr = FeatureLayer(service['url'], gis=gis)

                # GENERATE IDENTIFIERS
                idseq = service['id sequence']
                idfld = service['id field']
                if id_settings and idseq and idfld:
                    if idseq in id_settings:
                        new_sequence_value = add_identifiers(lyr, idseq, idfld)
                        id_settings[idseq]['next value'] = new_sequence_value
                    else:
                        _add_message('Sequence {} not found in sequence settings'.format(idseq), 'WARNING')

                # ENRICH REPORTS
                if service['enrichment']:
                    # reversed, sorted list of enrichment settings
                    enrich_settings = sorted(service['enrichment'], key=lambda k: k['priority'], reverse=True)
                    for reflayer in enrich_settings:
                        source_features = FeatureLayer(reflayer['url'], gis)
                        enrich_layer(source_features, lyr, reflayer)

                # MODERATION
                if modlists:
                    for query in service['moderation']:
                        if query['list'] in modlists:
                            moderate_features(lyr, query)
                        else:
                            _add_message('Moderation list {} not found in moderation settings'.format(modlist), 'WARNING')

                # SEND EMAILS
                if service['email']:
                    print(service['email'])
                else:
                    print('EXCEPTION')
                    print(service['email'])

                if service['email']:
                    regex = re.compile(r"([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\"([]!#-[^-~ \t]|(\\[\t -~]))+\")@([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\[[\t -Z^-~]*])")
                    with mailserver(server, username, password, tls) as email_server:
                        for message in service['email']:
                            rows = _get_features(lyr, message['sql'])

                            for row in rows:
                                address, subject, body = build_email(row, lyr.properties.fields, message)
                                if re.fullmatch(regex, address):

                                    if address and subject and body:
                                        try:
                                            sendemail(smtp=email_server, from_address=from_address,
                                                      reply_to=reply_to,
                                                      to_addresses=[address],
                                                      subject=subject,
                                                      email_body=body)

                                            row.attributes[message['field']] = message['sent value']
                                        except:
                                            _add_message('email failed to send for feature {} in layer {}'.format(row.attributes, service['url']))
                                else:
                                    _add_message('email was invalid for feature {} in layer {}'.format(row.attributes, service['url']))

                            if rows:
                                results = lyr.edit_features(updates=rows)
                                _report_failures(results)

            except Exception as ex:
                _add_message('Failed to process service {}\n{}'.format(service['url'], ex))

    except Exception as ex:
        _add_message('Failed. Please verify all configuration values\n{}'.format(ex))

    finally:
        # Close the email server
        email_server.close()
        new_sequences = [{'name': seq,
                          'interval': id_settings[seq]['interval'],
                          'next value': id_settings[seq]['next value'],
                          'pattern': id_settings[seq]['pattern']} for seq in id_settings]

        if not new_sequences == cfg['id sequences']:
            cfg['id sequences'] = new_sequences
            try:
                with open(configuration_file, 'w') as configfile:
                    json.dump(cfg, configfile)

            except Exception as ex:
                _add_message('Failed to save identifier configuration values.\n{}\nOld values:{}\nNew values:{}'.format(ex, cfg['id sequences'], new_sequences))
        return gisconn


if __name__ == '__main__':
    #print(path.join(path.dirname(__file__), 'servicefunctions.json'))
    gis1 = main(path.join(path.dirname(__file__), 'servicefunctions.json'))
    #time.sleep(5)
    print('Finished service functions. Importing to workforce...')
    ImportWorkOrders.importwo(gis1)
