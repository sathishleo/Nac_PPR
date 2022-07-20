import requests

from nwisefin.settings import SERVER_IP
import json

class Userservice:
    def branch_data(self, request):
        token_name = request.headers['Authorization']
        headers = {'Authorization': token_name}
        serverport_ip = SERVER_IP
        # api_url = api_jsondata.pop('api_url')
        full_url = serverport_ip + '/usrserv/fetch_employeebranch_id_code'
        api_jsondata = {"branch_id":[],"branch_code":[]}

        api_jsondata = json.dumps(api_jsondata)
        response = requests.post(full_url, headers=headers,data=api_jsondata, verify=False)
        return response

class Masterservice:
    def get_asset_data(self, request):
        token_name = request.headers['Authorization']
        headers = {'Authorization': token_name}
        serverport_ip = SERVER_IP
        # api_url = api_jsondata.pop('api_url')
        full_url = serverport_ip + '/usrserv/fetch_businesssegment_id_code'
        api_jsondata = {"branch_id": [], "branch_code": []}

        api_jsondata = json.dumps(api_jsondata)
        response = requests.post(full_url, headers=headers, data=api_jsondata, verify=False)
        return response
    def get_product_data(self, request):
        token_name = request.headers['Authorization']
        headers = {'Authorization': token_name}
        serverport_ip = SERVER_IP
        # api_url = api_jsondata.pop('api_url')
        full_url = serverport_ip + '/mstserv/fetch_product_id_code'
        api_jsondata = {"product_id":[],"product_code":[],"product_name":[]}

        api_jsondata = json.dumps(api_jsondata)
        response = requests.post(full_url, headers=headers, data=api_jsondata, verify=False)
        return response

    def get_client_data(self, request):
        token_name = request.headers['Authorization']
        headers = {'Authorization': token_name}
        serverport_ip = SERVER_IP
        # api_url = api_jsondata.pop('api_url')
        full_url = serverport_ip + '/mstserv/fetch_client_id_code'
        api_jsondata = {"client_id":[],"client_code":[],"client_name":[]}

        api_jsondata = json.dumps(api_jsondata)
        response = requests.post(full_url, headers=headers, data=api_jsondata, verify=False)
        return response

    def get_biz_data(self, request):
        token_name = request.headers['Authorization']
        headers = {'Authorization': token_name}
        serverport_ip = SERVER_IP
        # api_url = api_jsondata.pop('api_url')
        full_url = serverport_ip + '/mstserv/fetch_masterbusinesssegment_id_code'
        api_jsondata = {"bs_id":[],"bs_code":[],"bs_name":[]}

        api_jsondata = json.dumps(api_jsondata)
        response = requests.post(full_url, headers=headers, data=api_jsondata, verify=False)
        return response

