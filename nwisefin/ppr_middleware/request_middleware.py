from rest_framework import authentication, exceptions
# from middleware.nwisefinauth import NWisefinAuth
import requests
import json
from nwisefin.settings import SERVER_IP
class NWisefinAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        token_name = request.headers['Authorization']
        headers = {'Authorization': token_name}
        serverport_ip = SERVER_IP
        # api_url = api_jsondata.pop('api_url')
        full_url = serverport_ip+'/usrserv/micro_authentication'
        api_jsondata={}
        api_jsondata = json.dumps(api_jsondata, indent=2)
        resp = requests.post(full_url, headers=headers, data=api_jsondata, verify=False)
        api_resp = json.loads(resp.content)
        request.user_id=api_resp["user_id"]
        request.employee_id = api_resp["employee_id"]
        request.token = api_resp["token"]
        request.entity_info = api_resp["entity_info"]
        request.employee_id = api_resp["employee_id"]
        request.default_dict=api_resp["default"]
        request.entity_info = api_resp["entity_info"]
        request.token = api_resp["token"]
        request.scope =api_resp["scope"]
        self.nwisefin_authenticate(request,api_resp)
        if request.user is None:
                raise exceptions.AuthenticationFailed('Invalid credentials/token.')
        else:
            return request.user, None

    def nwisefin_authenticate(self, request,ape_resp):
        from knox.auth import TokenAuthentication
        if 'Authorization' in request.headers:
            token = request.META['HTTP_AUTHORIZATION']
            token_arr = token.split()
            if len(token_arr) == 2 and token_arr[0] == 'Token':
                token = token_arr[1]
        else:
            token = request.GET.get('token', None)
        if token is not None:
            token_auth_obj = TokenAuthentication()
            token_utf8 = token.encode("utf-8")
            try:
                token_obj = ape_resp['user']
                if token_obj is not None:
                    user = token_obj
                    request.user = user
            except Exception as e:
                request.user = None
        else:
            request.user = None
