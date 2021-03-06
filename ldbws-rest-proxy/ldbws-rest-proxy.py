# Proxy server to hide the horribleness of SOAP from clients.
# Presents a REST interface to clients

# Currently implements GetDepartureBoard(), getArrivalBoard() and GetServiceDetails()

from suds.client import Client
from suds.sax.element import Element
from os import environ
from os.path import expanduser, join
from flask import Flask, jsonify, make_response, abort
import logging

app = Flask(__name__)

logging.basicConfig(filename='ldbws-rest-proxy.log', level=logging.INFO)
#logging.getLogger('suds.client').setLevel(logging.DEBUG)

access_token_path = join(expanduser("~"), '.ldbws-access-token')


def contents_of(path):
    with open(path, 'r') as f:
        return f.read().strip()

access_token = environ.get('LDBWS_ACCESS_TOKEN')
if access_token is None:
    access_token = contents_of(access_token_path)


@app.errorhandler(500)
def internal_error(error):
    return make_response(jsonify({'error': 'Internal error'}), 500)


def string(x):
    return x


def datetime(x):
    return x.isoformat()


def extract_fields(source, *data):
    r = {}
    for o in data:
        field = o[0]
        parser = o[1]
        if field in source:
            r[field] = parser(source[field])
    return r


def extract_list(x, field, parser):
    if field in x:
        return [parser(i) for i in x[field]]
    else:
        return []


def service_location(x):
    return extract_fields(x,
                          ('futureChangeTo', string),
                          ('via', string),
                          ('crs', string),
                          ('locationName', string),
                          ('assoclsCancelled', string))


def service_locations(x):
    return extract_list(x, 'location', service_location)


def adhoc_alerts(x):
    return extract_list(x, 'adhocAlertText', string)


def service_item(x):
    return extract_fields(x,
                          ('sta', string),
                          ('eta', string),
                          ('std', string),
                          ('etd', string),
                          ('platform', string),
                          ('operator', string),
                          ('operatorCode', string),
                          ('isCircularRoute', string),
                          ('serviceID', string),
                          ('origin', service_locations),
                          ('destination', service_locations),
                          ('adhocAlerts', adhoc_alerts))


def service_items(x):
    return extract_list(x, 'service', service_item)


def nrcc_messages(x):
    return extract_list(x, 'message', string)


def station_board(x):
    return extract_fields(x,
                          ('generatedAt', datetime),
                          ('locationName', string),
                          ('crs', string),
                          ('filterLocationName', string),
                          ('filtercrs', string),
                          ('filterType', string),
                          ('platformAvailable', string),
                          ('areServicesAvailable', string),
                          ('trainServices', service_items),
                          ('busServices', service_items),
                          ('ferryServices', service_items),
                          ('nrccMessages', nrcc_messages))


def calling_points(x):
    return extract_fields(x,
                          ('locationName', string),
                          ('crs', string),
                          ('st', string),
                          ('et', string),
                          ('at', string),
                          ('adhocAlerts', adhoc_alerts))


def calling_points_list(x):
    return extract_list(x, 'callingPoint', calling_points)


def calling_points_list_list(x):
    return extract_list(x, 'callingPointList', calling_points_list)


def service_details(x):
    return extract_fields(x,
                          ('generatedAt', datetime),
                          ('serviceType', string),
                          ('locationName', string),
                          ('crs', string),
                          ('operator', string),
                          ('operatorCode', string),
                          ('isCancelled', string),
                          ('disruptionReason', string),
                          ('overdueMessage', string),
                          ('platform', string),
                          ('sta', string),
                          ('eta', string),
                          ('ata', string),
                          ('std', string),
                          ('etd', string),
                          ('atd', string),
                          ('adhocAlerts', adhoc_alerts),
                          ('previousCallingPoints', calling_points_list_list),
                          ('subsequentCallingPoints', calling_points_list_list))


def get_service():
    client = Client('https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2014-02-20')

    ns_common_types = ('com', 'http://thalesgroup.com/RTTI/2010-11-01/ldb/commontypes')
    el_token_value = Element('TokenValue', ns=ns_common_types)
    el_token_value.setText(access_token)

    el_access_token = Element('AccessToken', ns=ns_common_types).insert(el_token_value)
    client.set_options(soapheaders=el_access_token)

    return client.service


@app.route('/ldbws-rest-proxy/v0.1/departure-board/<string:from_crs>', methods=['GET'])
def get_departure_board_from(from_crs):
    try:
        soap_response = get_service().GetDepartureBoard(numRows=50, crs=from_crs)
        resp = station_board(soap_response)
        return jsonify(resp)
    except Exception as e:
        logging.error(e.message)
        abort(500)


@app.route('/ldbws-rest-proxy/v0.1/departure-board/<string:from_crs>/<string:to_crs>', methods=['GET'])
def get_departure_board_from_to(from_crs, to_crs):
    try:
        soap_response = get_service().GetDepartureBoard(numRows=50, crs=from_crs, filterCrs=to_crs, filterType='to')
        resp = station_board(soap_response)
        return jsonify(resp)
    except Exception as e:
        logging.error(e.message)
        abort(500)


@app.route('/ldbws-rest-proxy/v0.1/arrival-board/<string:to_crs>', methods=['GET'])
def get_arrival_board_to(to_crs):
    try:
        soap_response = get_service().GetArrivalBoard(numRows=50, crs=to_crs)
        resp = station_board(soap_response)
        return jsonify(resp)
    except Exception as e:
        logging.error(e.message)
        abort(500)


@app.route('/ldbws-rest-proxy/v0.1/arrival-board/<string:to_crs>/<string:from_crs>', methods=['GET'])
def get_arrival_board_to_from(to_crs, from_crs):
    try:
        soap_response = get_service().GetArrivalBoard(numRows=50, crs=to_crs, filterCrs=from_crs, filterType='from')
        resp = station_board(soap_response)
        return jsonify(resp)
    except Exception as e:
        logging.error(e.message)
        abort(500)


@app.route('/ldbws-rest-proxy/v0.1/service-details/<path:service_id>', methods=['GET'])
def get_service_details(service_id):
    try:
        soap_response = get_service().GetServiceDetails(serviceID=service_id)
        resp = service_details(soap_response)
        return jsonify(resp)
    except Exception as e:
        logging.error(e.message)
        abort(500)


if __name__ == '__main__':
    app.run(debug=False)
