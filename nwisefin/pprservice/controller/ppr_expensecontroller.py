# from django.views.decorators.csrf import csrf_exempt
# from rest_framework.decorators import api_view
# from django.views.decorators.csrf import csrf_exempt
# from rest_framework.decorators import api_view, authentication_classes, permission_classes
# from django.http import HttpResponse, JsonResponse
# from pprservice.data.request.nac_income_request import ppr_clientrequest
# from pprservice.util.pprutility import MASTER_SERVICE
#
# from utilityservice.data.response.nwisefinpage import NWisefinPage
# from utilityservice.service.nwisefinauthenticate import NWisefinAuthentication
# from utilityservice.service.nwisefinpermission import NWisefinPermission
# from rest_framework.permissions import IsAuthenticated
# from pprservice.service.dss_service import DSS_Service
# import json
# from pprservice.data.request.nac_income_request import ppr_clientrequest, ppr_source_request
# @csrf_exempt
# @api_view(['POST'])
# @authentication_classes([NWisefinAuthentication])
# @permission_classes([IsAuthenticated, NWisefinPermission])
# def ppr_expense(request):
#     scope = request.scope
#     if request.method == 'POST':
#         filter_obj = json.loads(request.body)
#         filter_obj = ppr_source_request(filter_obj)
#         pprservice = DSS_Service(scope)
#         ppr_data = pprservice.fetch_dssdate_level_list(filter_obj)
#         response = HttpResponse(ppr_data.get(), content_type="application/json")
#         return response
