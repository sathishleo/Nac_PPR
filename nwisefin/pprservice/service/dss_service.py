import json
from datetime import timedelta

import numpy as np
import pandas as pd
import requests
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse

from pprservice.data.request.nac_income_request import ppr_clientrequest

from utilityservice.data.response.nwisefinerror import NWisefinError
from utilityservice.data.response.nwisefinerrorconstants import ErrorMessage, ErrorDescription
from utilityservice.data.response.nwisefinlist import NWisefinList
from utilityservice.data.response.nwisefinpaginator import NWisefinPaginator
from utilityservice.data.response.nwisefinsuccess import NWisefinSuccess, SuccessMessage, SuccessStatus
from utilityservice.service.threadlocal import NWisefinThread
from utilityservice.service.applicationconstants import ApplicationNamespace
from pprservice.models.pprmodel import DSS_Format_Date,DSS_Format_Month,Ppr_Sources,Head_Groups,Sub_Groups,GL_Subgroup
from pprservice.util.pprutility import Fees_type, Client_flag, Activestatus, Asset_class, USER_SERVICE
from pprservice.data.response.nac_income_respone import ppr_clientresponse,Income_details_response as Income_details_response
from datetime import datetime
from pprservice.data.response.nac_income_respone import ppr_clientresponse, \
    Income_details_response as Income_details_response, ppr_source_response
from wisefinapi.internal.tokenhandler import TokenHandler
from nwisefin.settings import SERVER_IP

class DSS_Service(NWisefinThread):
    def __init__(self, scope):
        super().__init__(scope)
        self._set_namespace(ApplicationNamespace.PPR_SERVICE)

    def dss_upload_date(self, dssfile_obj, emp_id):
        gl_data = GL_Subgroup.objects.using(self._current_app_schema()).filter(status=1)
        gl_df = pd.DataFrame(gl_data.values('id', 'gl_no'))
        data_type = {"id": int, "gl_no": int}
        gl_df = gl_df.astype(data_type)
        # dssfile_obj['gl_no'].astype(str)
        merge_data = pd.merge(gl_df, dssfile_obj,
                              on="gl_no", how="right",
                              )
        nan_values = merge_data[merge_data['id'].isna()]
        merge_data = merge_data.dropna(subset=['id'])
        dss_obj = merge_data.fillna(np.nan).replace([np.nan], [0]).to_dict(orient='records')
        dss_obj1 = nan_values.to_dict(orient='records')
        # month_tab=self.dss_upload_month(dss_obj,emp_id)
        # dssfile_obj.gl_no.update(dssfile_obj.gl_no.map(gl_df.set_index('gl_no').id), ignore_index=True)
        # file_obj = dssfile_obj
        for file_data in dss_obj:
            month_tab = self.dss_upload_month(file_data, emp_id)
            if file_data["id"] != 0:
                obj = DSS_Format_Date.objects.using(self._current_app_schema()).filter(gl_subgroup=file_data["id"],
                                                                                       entity_id=self._entity_id(),
                                                                                       flag=1, date=file_data["date"])
                # if len(obj) != 0: `
                #     dss_obj = DSS_Format_Date.objects.using(self._current_app_schema()).filter(
                #         gl_subgroup_id=file_data["id"],date=file_data["date"], entity_id=self._entity_id()).update(
                #         credit=F('credit') + file_data["Credits"], debit=F('debit') + file_data["Debits"],
                #         opening_balance=F('opening_balance') + file_data["Beginning Balance"],
                #         closing_balance=F('closing_balance') + file_data["Ending Balance"],status=1,
                #         updated_by=emp_id, updated_date=datetime.now(), date=file_data["date"],
                #         entity_id=self._entity_id(), flag=1)
                if len(obj) != 0:
                    dss_obj = DSS_Format_Date.objects.using(self._current_app_schema()).filter(
                        gl_subgroup_id=file_data["id"],date=file_data["date"], entity_id=self._entity_id()).update(
                        credit=F('credit') + file_data["Credits"], debit=file_data["Debits"],
                        opening_balance=file_data["Beginning Balance"],
                        closing_balance=file_data["Ending Balance"],status=1,
                        updated_by=emp_id, updated_date=datetime.now(), date=file_data["date"],
                        entity_id=self._entity_id(), flag=1)
                else:
                    dss_obj = DSS_Format_Date.objects.using(self._current_app_schema()).create(
                        credit=file_data["Credits"],
                        debit=file_data["Debits"], opening_balance=file_data["Beginning Balance"],
                        date=file_data["date"], closing_balance=file_data["Ending Balance"], status=1,
                        created_by=emp_id, created_date=datetime.now(), gl_subgroup_id=file_data["id"],
                        entity_id=self._entity_id(), flag=1)
            else:
                dss_obj = DSS_Format_Date.objects.using(self._current_app_schema()).create(credit=file_data["Credits"],
                                                                                           debit=file_data["Debits"],
                                                                                           opening_balance=file_data[
                                                                                               "Beginning Balance"],
                                                                                           date=file_data["date"],
                                                                                           closing_balance=file_data[
                                                                                               "Ending Balance"],
                                                                                           status=1, created_by=emp_id,
                                                                                           created_date=datetime.now(),
                                                                                           gl_subgroup_id=None,
                                                                                           entity_id=self._entity_id(),
                                                                                           flag=2)

        data_list = NWisefinList()
        for data in dss_obj1:
            ppr_response = ppr_source_response()
            ppr_response.set_gl_no(data["gl_no"])
            ppr_response.set_description(data["Description"])
            ppr_response.set_debit(data["Debits"])
            ppr_response.set_credit(data["Credits"])
            ppr_response.set_closing_balance(data["Ending Balance"])
            ppr_response.set_opening_balance(data["Beginning Balance"])
            data_list.append(ppr_response)
        success_obj = NWisefinSuccess()
        success_obj.set_status(SuccessStatus.SUCCESS)
        # success_obj.set_message(list(dss_obj1))
        success_obj.set_message(data_list)
        return success_obj

    def dss_upload_month(self, file_data, emp_id):
        # date=file_data["date"]
        # datem = file_data["date"].month
        month = file_data["date"].month
        if file_data["id"] != 0:
            obj = DSS_Format_Month.objects.using(self._current_app_schema()).filter(gl_subgroup=file_data["id"],
                                                                                    entity_id=self._entity_id(),
                                                                                    flag=1, month=month)
            if len(obj) != 0:
                dss_obj = DSS_Format_Month.objects.using(self._current_app_schema()).filter(
                    gl_subgroup_id=file_data["id"],month=month, entity_id=self._entity_id()).update(
                    credit=file_data["Credits"], debit=file_data["Debits"],
                    opening_balance=file_data["Beginning Balance"],
                    closing_balance=file_data["Ending Balance"], month=month, status=1,
                    updated_by=emp_id, updated_date=datetime.now(),
                    entity_id=self._entity_id(), flag=1)
            else:
                dss_obj = DSS_Format_Month.objects.using(self._current_app_schema()).create(
                    credit=file_data["Credits"],
                    debit=file_data["Debits"], opening_balance=file_data["Beginning Balance"], month=month,
                    closing_balance=file_data["Ending Balance"], status=1, created_by=emp_id,
                    created_date=datetime.now(), gl_subgroup_id=file_data["id"], entity_id=self._entity_id(),
                    flag=1)
        else:
            dss_obj = DSS_Format_Month.objects.using(self._current_app_schema()).create(credit=file_data["Credits"],
                                                                                        debit=file_data["Debits"],
                                                                                        opening_balance=file_data[
                                                                                            "Beginning Balance"],
                                                                                        month=month,
                                                                                        closing_balance=file_data[
                                                                                            "Ending Balance"],
                                                                                        status=1, created_by=emp_id,
                                                                                        created_date=datetime.now(),
                                                                                        gl_subgroup_id=None,
                                                                                        entity_id=self._entity_id(),
                                                                                        flag=2)

    def fetch_dssdate_level_list(self, filterobj):
        prolist = NWisefinList()
        prolist1 = NWisefinList()
        prolist2 = NWisefinList()
        befo_date = filterobj.get_date()
        input_date = datetime.strptime(befo_date, "%Y-%m-%d")
        input_date = input_date.date()
        day = timedelta(days=1)
        prev_date = input_date - day
        month = input_date.replace(day=1)
        prev_month = month - day
        condition = Q(status=1)&Q( date__date=input_date)&(Q(gl_subgroup__gl_no__startswith='1') | Q(gl_subgroup__gl_no__startswith='2'))
        condition2 = Q(status=1, date__date=input_date,
                       gl_subgroup__head_group__head_group__source_id=filterobj.get_id())
        condition3 = Q(status=1, date__date=input_date, gl_subgroup__head_group__head_group_id=filterobj.get_id())
        condition4 = Q(status=1, date__date=input_date, gl_subgroup__head_group_id=filterobj.get_id())

        othergl_openbal = 0.00
        othergl_closebal = 0.00
        othergl_credit = 0.00
        othergl_debit = 0.00

        if filterobj.get_type() != None and filterobj.get_type() != "":
            if filterobj.get_type() == 1:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition).values(
                    'date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(credit=Sum('credit'),
                                                                                                 debit=Sum('debit'),
                                                                                                 opening_balance=Sum(
                                                                                                     'opening_balance'),
                                                                                                 closing_balance=Sum(
                                                                                                     'closing_balance'))
            if filterobj.get_type() == 2:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition2).values(
                    'date__date', "gl_subgroup__head_group__head_group__id","gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__name").annotate(credit=Sum('credit'),
                                                                                         debit=Sum('debit'),
                                                                                         opening_balance=Sum(
                                                                                             'opening_balance'),
                                                                                         closing_balance=Sum(
                                                                                             'closing_balance'))
            if filterobj.get_type() == 3:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition3).values(
                    'date__date', "gl_subgroup__head_group__id", "gl_subgroup__head_group__name","gl_subgroup__head_group__head_group__source__id").annotate(
                    credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                    closing_balance=Sum('closing_balance'))
            if filterobj.get_type() == 4:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition4).values(
                'date__date', "gl_subgroup__id", "gl_subgroup__description", "gl_subgroup__gl_no","gl_subgroup__head_group__head_group__source__id").annotate(
                credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                closing_balance=Sum('closing_balance'))
        arr1 = []
        arr2 = []
        data1 = []
        data2 = []
        value = []
        if len(filter_var) != 0:
            condition = Q(status=1, date__date=input_date)
            gl4_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                              gl_subgroup__gl_no__startswith='4') \
                .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                        "gl_subgroup__head_group__head_group__source__name").annotate(
                credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                closing_balance=Sum('closing_balance'))
            gl3_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                              gl_subgroup__gl_no__startswith='3') \
                .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                        "gl_subgroup__head_group__head_group__source__name").annotate(
                credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                closing_balance=Sum('closing_balance'))
            for gl3, gl4 in zip(gl3_dss_amount, gl4_dss_amount):
                othergl_openbal = gl3["opening_balance"] + gl4["opening_balance"]
                othergl_closebal = gl3["closing_balance"] + gl4["closing_balance"]
                othergl_credit = gl3["credit"] + gl4["credit"]
                othergl_debit = gl3["debit"] + gl4["debit"]
            for i in filter_var:
                ppr_response = ppr_source_response()
                if filterobj.get_type() == 1:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101,status=1)
                    gl_source_value = gl_source_obj.head_group.head_group.source_id
                    ppr_response.set_name(i["gl_subgroup__head_group__head_group__source__name"])
                    name = i["gl_subgroup__head_group__head_group__source__name"]
                    id_grp = i["gl_subgroup__head_group__head_group__source__id"]
                    if gl_source_value == i["gl_subgroup__head_group__head_group__source__id"]:
                        ppr_response.set_opening_balance(i["opening_balance"]*-1+othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"]*-1+othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"]*-1+othergl_credit*-1)
                        ppr_response.set_debit(i["debit"]*-1+othergl_debit*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist.append(data1)
                elif filterobj.get_type() == 2:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    gl_source_value = gl_source_obj.head_group.head_group_id
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    ppr_response.set_name(i["gl_subgroup__head_group__head_group__name"])
                    ppr_response.set_id(i["gl_subgroup__head_group__head_group__id"])
                    name = i["gl_subgroup__head_group__head_group__name"]
                    id_grp = i["gl_subgroup__head_group__head_group__id"]
                    if gl_source_value == id_grp:
                        ppr_response.set_opening_balance(i["opening_balance"] * -1 + othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"] * -1 + othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"] * -1 + othergl_credit*-1)
                        ppr_response.set_debit(i["debit"] * -1 + othergl_debit*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_opening_balance(i["opening_balance"]*-1)
                        ppr_response.set_closing_balance(i["closing_balance"]*-1)
                        ppr_response.set_credit(i["credit"]*-1)
                        ppr_response.set_debit(i["debit"]*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist.append(data1)
                elif filterobj.get_type() == 3:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.head_group_id
                    ppr_response.set_name(i["gl_subgroup__head_group__name"])
                    ppr_response.set_id(i["gl_subgroup__head_group__id"])
                    name = i["gl_subgroup__head_group__name"]
                    id_grp = i["gl_subgroup__head_group__id"]
                    if gl_source_value == id_grp:
                        ppr_response.set_opening_balance(i["opening_balance"] * -1 + othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"] * -1 + othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"] * -1 + othergl_credit*-1)
                        ppr_response.set_debit(i["debit"] * -1 + othergl_debit*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_opening_balance(i["opening_balance"]*-1)
                        ppr_response.set_closing_balance(i["closing_balance"]*-1)
                        ppr_response.set_credit(i["credit"]*-1)
                        ppr_response.set_debit(i["debit"]*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist.append(data1)
                elif filterobj.get_type() == 4:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.id
                    ppr_response.set_name(i["gl_subgroup__gl_no"]+" -("+str(i['gl_subgroup__description'])+")")
                    name = i["gl_subgroup__gl_no"]+" -("+str(i['gl_subgroup__description'])+")"
                    id_grp = i["gl_subgroup__id"]
                    ppr_response.set_description(i["gl_subgroup__description"])
                    if gl_source_value == id_grp:
                        ppr_response.set_opening_balance(i["opening_balance"] * -1 + othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"] * -1 + othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"] * -1 + othergl_credit*-1)
                        ppr_response.set_debit(i["debit"] * -1 + othergl_debit*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_opening_balance(i["opening_balance"]*-1)
                        ppr_response.set_closing_balance(i["closing_balance"]*-1)
                        ppr_response.set_credit(i["credit"]*-1)
                        ppr_response.set_debit(i["debit"]*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist.append(data1)
        # return prolist
        # condition = Q(status=1, date__date=prev_date)
        condition = Q(status=1) & Q(date__date=prev_date) & (
                    Q(gl_subgroup__gl_no__startswith='1') | Q(gl_subgroup__gl_no__startswith='2'))
        condition2 = Q(status=1, date__date=prev_date,
                       gl_subgroup__head_group__head_group__source_id=filterobj.get_id())
        condition3 = Q(status=1, date__date=prev_date, gl_subgroup__head_group__head_group_id=filterobj.get_id())
        condition4 = Q(status=1, date__date=prev_date, gl_subgroup__head_group_id=filterobj.get_id())
        if filterobj.get_type() != None and filterobj.get_type() != "":
            if filterobj.get_type() == 1:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition).values(
                    'date__date', "gl_subgroup__head_group__head_group__source__id","gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(credit=Sum('credit'),
                                                                                                 debit=Sum('debit'),
                                                                                                 opening_balance=Sum(
                                                                                                     'opening_balance'),
                                                                                                 closing_balance=Sum(
                                                                                                     'closing_balance'))
            if filterobj.get_type() == 2:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition2).values(
                    'date__date', "gl_subgroup__head_group__head_group__id","gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__name").annotate(credit=Sum('credit'),
                                                                                         debit=Sum('debit'),
                                                                                         opening_balance=Sum(
                                                                                             'opening_balance'),
                                                                                         closing_balance=Sum(
                                                                                             'closing_balance'))
            if filterobj.get_type() == 3:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition3).values(
                    'date__date', "gl_subgroup__head_group__id", "gl_subgroup__head_group__name","gl_subgroup__head_group__head_group__source__id").annotate(
                    credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                    closing_balance=Sum('closing_balance'))
            if filterobj.get_type() == 4:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition4).values(
                        'date__date', "gl_subgroup__id", "gl_subgroup__description", "gl_subgroup__gl_no","gl_subgroup__head_group__head_group__source__id").annotate(
                        credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                        closing_balance=Sum('closing_balance'))
        arr1 = []
        arr2 = []
        data1 = []
        data2 = []
        value = []
        if len(filter_var) != 0:
            condition = Q(status=1, date__date=prev_date)
            gl4_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                              gl_subgroup__gl_no__startswith='4') \
                .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                        "gl_subgroup__head_group__head_group__source__name").annotate(
                credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                closing_balance=Sum('closing_balance'))
            gl3_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                              gl_subgroup__gl_no__startswith='3') \
                .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                        "gl_subgroup__head_group__head_group__source__name").annotate(
                credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                closing_balance=Sum('closing_balance'))
            for gl3, gl4 in zip(gl3_dss_amount, gl4_dss_amount):
                othergl_openbal = gl3["opening_balance"] + gl4["opening_balance"]
                othergl_closebal = gl3["closing_balance"] + gl4["closing_balance"]
                othergl_credit = gl3["credit"] + gl4["credit"]
                othergl_debit = gl3["debit"] + gl4["debit"]
            for i in filter_var:
                ppr_response = ppr_source_response()
                if filterobj.get_type() == 1:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    gl_source_value = gl_source_obj.head_group.head_group.source_id
                    ppr_response.set_name(i["gl_subgroup__head_group__head_group__source__name"])
                    name = i["gl_subgroup__head_group__head_group__source__name"]
                    id_grp = i["gl_subgroup__head_group__head_group__source__id"]
                    if gl_source_value == id_grp:
                        ppr_response.set_opening_balance(i["opening_balance"] * -1 + othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"] * -1 + othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"] * -1 + othergl_credit*-1)
                        ppr_response.set_debit(i["debit"] * -1 + othergl_debit*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist1.append(data1)
                elif filterobj.get_type() == 2:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.head_group.head_group_id
                    ppr_response.set_name(i["gl_subgroup__head_group__head_group__name"])
                    ppr_response.set_id(i["gl_subgroup__head_group__head_group__id"])
                    name = i["gl_subgroup__head_group__head_group__name"]
                    id_grp = i["gl_subgroup__head_group__head_group__id"]
                    if gl_source_value == id_grp:
                        ppr_response.set_opening_balance(i["opening_balance"] * -1 + othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"] * -1 + othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"] * -1 + othergl_credit*-1)
                        ppr_response.set_debit(i["debit"] * -1 + othergl_debit*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_opening_balance(i["opening_balance"]*-1)
                        ppr_response.set_closing_balance(i["closing_balance"]*-1)
                        ppr_response.set_credit(i["credit"]*-1)
                        ppr_response.set_debit(i["debit"]*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist1.append(data1)
                elif filterobj.get_type() == 3:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.head_group_id
                    ppr_response.set_name(i["gl_subgroup__head_group__name"])
                    ppr_response.set_id(i["gl_subgroup__head_group__id"])
                    name = i["gl_subgroup__head_group__name"]
                    id_grp = i["gl_subgroup__head_group__id"]
                    if gl_source_value == id_grp:
                        ppr_response.set_opening_balance(i["opening_balance"] * -1 + othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"] * -1 + othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"] * -1 + othergl_credit*-1)
                        ppr_response.set_debit(i["debit"] * -1 + othergl_debit*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_opening_balance(i["opening_balance"]*-1)
                        ppr_response.set_closing_balance(i["closing_balance"]*-1)
                        ppr_response.set_credit(i["credit"]*-1)
                        ppr_response.set_debit(i["debit"]*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist1.append(data1)
                elif filterobj.get_type() == 4:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.id
                    ppr_response.set_name(i["gl_subgroup__gl_no"]+" -("+str(i['gl_subgroup__description'])+")")
                    name = i["gl_subgroup__gl_no"]+" -("+str(i['gl_subgroup__description'])+")"
                    id_grp = i["gl_subgroup__id"]
                    ppr_response.set_description(i["gl_subgroup__description"])
                    if gl_source_value == id_grp:
                        ppr_response.set_opening_balance(i["opening_balance"] * -1 + othergl_openbal*-1)
                        ppr_response.set_closing_balance(i["closing_balance"] * -1 + othergl_closebal*-1)
                        ppr_response.set_credit(i["credit"] * -1 + othergl_credit*-1)
                        ppr_response.set_debit(i["debit"] * -1 + othergl_debit*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_opening_balance(i["opening_balance"]*-1)
                        ppr_response.set_closing_balance(i["closing_balance"]*-1)
                        ppr_response.set_credit(i["credit"]*-1)
                        ppr_response.set_debit(i["debit"]*-1)
                    else:
                        ppr_response.set_opening_balance(i["opening_balance"])
                        ppr_response.set_closing_balance(i["closing_balance"])
                        ppr_response.set_credit(i["credit"])
                        ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist1.append(data1)
        a=prolist.data
        b=prolist1.data
        resp_list=NWisefinList()
        arr=[]
        for i in a:
            # a=False
            for j in b:
                if i["id"]==j["id"]:
                    i["value"].append(j["value"][0])
                    resp_list.append(i)
                    arr.append(i["id"])
                #     resp_list.append(i)
                #     a=True
                # else:
                #     i["value"].append({"closing_balance": "", "credit": "", "date": "", "debit": "", "opening_balance": "",
                #              "id": "", "name": ""})

                #     resp_list.append(i)
        for i in a:
            if i["id"] not in arr:
                i["value"].append({"closing_balance": 0.00, "credit": 0.00, "date": str(prev_date), "debit": 0.00, "opening_balance": 0.00,
                             "id": "", "name": ""})
                resp_list.append(i)
        for j in b:
            if j["id"] not in arr:
                j["value"].insert(0,{"closing_balance": 0.00, "credit": 0.00, "date": str(input_date), "debit": 0.00, "opening_balance": 0.00,
                             "id": "", "name": ""})
                resp_list.append(j)
        # return resp_list
        # condition = Q(status=1, date__date=prev_month)
        condition = Q(status=1) & Q(date__date=prev_month) & (
                    Q(gl_subgroup__gl_no__startswith='1') | Q(gl_subgroup__gl_no__startswith='2'))
        condition2 = Q(status=1, date__date=prev_month,
                       gl_subgroup__head_group__head_group__source_id=filterobj.get_id())
        condition3 = Q(status=1, date__date=prev_month, gl_subgroup__head_group__head_group_id=filterobj.get_id())
        condition4 = Q(status=1, date__date=prev_month, gl_subgroup__head_group_id=filterobj.get_id())
        if filterobj.get_type() != None and filterobj.get_type() != "":
            if filterobj.get_type() == 1:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition).values(
                    'date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(credit=Sum('credit'),
                                                                                                 debit=Sum('debit'),
                                                                                                 opening_balance=Sum(
                                                                                                     'opening_balance'),
                                                                                                 closing_balance=Sum(
                                                                                                     'closing_balance'))
            if filterobj.get_type() == 2:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition2).values(
                    'date__date', "gl_subgroup__head_group__head_group__id","gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__name").annotate(credit=Sum('credit'),
                                                                                         debit=Sum('debit'),
                                                                                         opening_balance=Sum(
                                                                                             'opening_balance'),
                                                                                         closing_balance=Sum(
                                                                                             'closing_balance'))
            if filterobj.get_type() == 3:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition3).values(
                    'date__date', "gl_subgroup__head_group__id", "gl_subgroup__head_group__name","gl_subgroup__head_group__head_group__source__id").annotate(
                    credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                    closing_balance=Sum('closing_balance'))
            if filterobj.get_type() == 4:
                filter_var = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition4).values(
                    'date__date', "gl_subgroup__id", "gl_subgroup__gl_no","gl_subgroup__description","gl_subgroup__head_group__head_group__source__id").annotate(
                    credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                    closing_balance=Sum('closing_balance'))
        arr1 = []
        arr2 = []
        data1 = []
        data2 = []
        value = []
        if len(filter_var) != 0:
            condition = Q(status=1, date__date=prev_month)
            gl4_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                              gl_subgroup__gl_no__startswith='4') \
                .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                        "gl_subgroup__head_group__head_group__source__name").annotate(
                credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                closing_balance=Sum('closing_balance'))
            gl3_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                              gl_subgroup__gl_no__startswith='3') \
                .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                        "gl_subgroup__head_group__head_group__source__name").annotate(
                credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
                closing_balance=Sum('closing_balance'))
            for gl3, gl4 in zip(gl3_dss_amount, gl4_dss_amount):
                othergl_closebal = gl3["closing_balance"]+gl4["closing_balance"]
            for i in filter_var:
                ppr_response = ppr_source_response()
                if filterobj.get_type() == 1:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    gl_source_value = gl_source_obj.head_group.head_group.source_id
                    ppr_response.set_id(i["gl_subgroup__head_group__head_group__source__id"])
                    ppr_response.set_name(i["gl_subgroup__head_group__head_group__source__name"])
                    name = i["gl_subgroup__head_group__head_group__source__name"]
                    id_grp = i["gl_subgroup__head_group__head_group__source__id"]
                    # ppr_response.set_opening_balance(i["opening_balance"])
                    if gl_source_value == id_grp:
                        ppr_response.set_month_balance(i["closing_balance"]*-1+othergl_closebal*-1)
                    else:
                        ppr_response.set_month_balance(i["closing_balance"])
                    # ppr_response.set_credit(i["credit"])
                    # ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist2.append(data1)
                elif filterobj.get_type() == 2:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.head_group.head_group_id
                    ppr_response.set_id(i["gl_subgroup__head_group__head_group__id"])
                    ppr_response.set_name(i["gl_subgroup__head_group__head_group__name"])
                    name = i["gl_subgroup__head_group__head_group__name"]
                    id_grp = i["gl_subgroup__head_group__head_group__id"]
                    # ppr_response.set_opening_balance(i["opening_balance"])
                    if gl_source_value == id_grp:
                        ppr_response.set_month_balance(i["closing_balance"]*-1 + othergl_closebal*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_month_balance(i["closing_balance"]*-1)
                    else:
                        ppr_response.set_month_balance(i["closing_balance"])
                    # ppr_response.set_credit(i["credit"])
                    # ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist2.append(data1)
                elif filterobj.get_type() == 3:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.head_group_id
                    ppr_response.set_id(i["gl_subgroup__head_group__id"])
                    ppr_response.set_name(i["gl_subgroup__head_group__name"])
                    name = i["gl_subgroup__head_group__name"]
                    id_grp = i["gl_subgroup__head_group__id"]
                    # ppr_response.set_opening_balance(i["opening_balance"])
                    if gl_source_value == id_grp:
                        ppr_response.set_month_balance(i["closing_balance"]*-1 + othergl_closebal*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_month_balance(i["closing_balance"]*-1)
                    else:
                        ppr_response.set_month_balance(i["closing_balance"])
                    # ppr_response.set_credit(i["credit"])
                    # ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist2.append(data1)
                elif filterobj.get_type() == 4:
                    a = 1000
                    # dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter()
                    gl_source_obj = GL_Subgroup.objects.using(self._current_app_schema()).get(gl_no=112101, status=1)
                    source_obj = Ppr_Sources.objects.using(self._current_app_schema()).get(name='Sources')
                    source_id = source_obj.id
                    gl_source_value = gl_source_obj.id
                    ppr_response.set_id(i["gl_subgroup__id"])
                    ppr_response.set_name(i["gl_subgroup__gl_no"])+" -("+str(i['gl_subgroup__description'])+")"
                    name = i["gl_subgroup__gl_no"]+" -("+str(i['gl_subgroup__description'])+")"
                    id_grp = i["gl_subgroup__id"]
                    ppr_response.set_description(i["gl_subgroup__description"])
                    # ppr_response.set_opening_balance(i["opening_balance"])
                    if gl_source_value == id_grp:
                        ppr_response.set_month_balance(i["closing_balance"]*-1 + othergl_closebal*-1)
                    elif i["gl_subgroup__head_group__head_group__source__id"]==source_id:
                        ppr_response.set_month_balance(i["closing_balance"]*-1)
                    else:
                        ppr_response.set_month_balance(i["closing_balance"])
                    # ppr_response.set_credit(i["credit"])
                    # ppr_response.set_debit(i["debit"])
                    ppr_response.set_date(str(i["date__date"]))
                    value.append(ppr_response)
                    data1 = {"name": name, "value": value, "id": id_grp}
                    value = []
                    prolist2.append(data1)
        c = resp_list.data
        d = prolist2.data
        resp_list1 = NWisefinList()
        arr3 = []
        for k in c:
            # a=False
            for l in d:
                if k["id"] ==l["id"]:
                    k["value"].append(l["value"][0])
                    resp_list1.append(k)
                    arr3.append(k["id"])
                #     resp_list.append(i)
                #     a=True
                # else:
                #     i["value"].append({"closing_balance": "", "credit": "", "date": "", "debit": "", "opening_balance": "",
                #              "id": "", "name": ""})

                #     resp_list.append(i)
        for i in c:
            if i["id"] not in arr3:
                i["value"].append(
                    {"month_balance": 0.00,"date": "",
                     "id": "", "name": ""})
                resp_list1.append(i)
        # for j in d:
        #     if j["id"] not in arr3:
        #         j["value"].append({"month_balance": "","date": str(input_date),
        #                               "id": "", "name": ""})
        #         resp_list1.append(j)
        return resp_list1

    def fetch_profitorloss_list(self,filter_obj):
        pro_list = NWisefinList()
        pro_list2 = NWisefinList()
        pro_list3 = NWisefinList()
        befo_date = filter_obj.get_date()
        input_date = datetime.strptime(befo_date, "%Y-%m-%d")
        input_date = input_date.date()
        day = timedelta(days=1)
        prev_date = input_date - day
        month = input_date.replace(day=1)
        prev_month = month - day
        condition = Q(status=1, date__date=input_date)
        othergl_openbal = 0.0
        othergl_closebal = 0.00
        othergl_credit = 0.00
        othergl_debit = 0.00
        date = input_date
        gl4_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                          gl_subgroup__gl_no__startswith='4') \
            .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(
            credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
            closing_balance=Sum('closing_balance'))
        gl3_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition,
                                                                                          gl_subgroup__gl_no__startswith='3') \
            .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(
            credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
            closing_balance=Sum('closing_balance'))
        value = []
        for gl3, gl4 in zip(gl3_dss_amount, gl4_dss_amount):
            othergl_openbal = gl3["opening_balance"]+gl4["opening_balance"]
            othergl_closebal = gl3["closing_balance"]+ gl4["closing_balance"]
            othergl_credit = gl3["credit"]+ gl4["credit"]
            othergl_debit = gl3["debit"]+ gl4["debit"]
            date = str(gl3["date__date"])
        ppr_response = ppr_source_response()
        if othergl_openbal != 0.0:
            ppr_response.set_opening_balance(othergl_openbal*-1)
        else:
            ppr_response.set_opening_balance(othergl_openbal)
        if othergl_closebal != 0.0:
            ppr_response.set_closing_balance(othergl_closebal * -1)
        else:
            ppr_response.set_closing_balance(othergl_closebal)
        if othergl_credit != 0.0:
            ppr_response.set_credit(othergl_credit*-1)
        else:
            ppr_response.set_credit(othergl_credit)
        if othergl_debit != 0.0:
            ppr_response.set_debit(othergl_debit*-1)
        else:
            ppr_response.set_debit(othergl_debit)
        ppr_response.set_date(str(date))
        value.append(ppr_response)
        data1 = {"name": "profitorloss", "value": value}
        # value = []
        pro_list.append(data1)

        condition2 = Q(status=1, date__date=prev_date)
        othergl_openbal = 0.0
        othergl_closebal = 0.00
        othergl_credit = 0.00
        othergl_debit = 0.00
        date = prev_date
        gl4_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition2,
                                                                                          gl_subgroup__gl_no__startswith='4') \
            .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(
            credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
            closing_balance=Sum('closing_balance'))
        gl3_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition2,
                                                                                          gl_subgroup__gl_no__startswith='3') \
            .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(
            credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
            closing_balance=Sum('closing_balance'))
        # value = []
        for gl3, gl4 in zip(gl3_dss_amount, gl4_dss_amount):
            othergl_openbal = gl3["opening_balance"] +gl4["opening_balance"]
            othergl_closebal = gl3["closing_balance"] + gl4["closing_balance"]
            othergl_credit = gl3["credit"] + gl4["credit"]
            othergl_debit = gl3["debit"] + gl4["debit"]
            date = str(gl3["date__date"])
        ppr_response = ppr_source_response()
        if othergl_openbal != 0.0:
            ppr_response.set_opening_balance(othergl_openbal * -1)
        else:
            ppr_response.set_opening_balance(othergl_openbal)
        if othergl_closebal != 0.0:
            ppr_response.set_closing_balance(othergl_closebal * -1)
        else:
            ppr_response.set_closing_balance(othergl_closebal)
        if othergl_credit != 0.0:
            ppr_response.set_credit(othergl_credit * -1)
        else:
            ppr_response.set_credit(othergl_credit)
        if othergl_debit != 0.0:
            ppr_response.set_debit(othergl_debit * -1)
        else:
            ppr_response.set_debit(othergl_debit)
        ppr_response.set_date(str(date))
        value.append(ppr_response)
        data1 = {"name": "profitorloss", "value": value}
        # value = []
        pro_list2.append(data1)

        condition3 = Q(status=1, date__date=prev_month)
        # othergl_openbal = 0.0
        othergl_closebal = 0.00
        # othergl_credit = 0.00
        # othergl_debit = 0.00
        date = prev_month
        gl4_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition3,
                                                                                          gl_subgroup__gl_no__startswith='4') \
            .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(
            credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
            closing_balance=Sum('closing_balance'))
        gl3_dss_amount = DSS_Format_Date.objects.using(self._current_app_schema()).filter(condition3,
                                                                                          gl_subgroup__gl_no__startswith='3') \
            .values('date__date', "gl_subgroup__head_group__head_group__source__id",
                    "gl_subgroup__head_group__head_group__source__name").annotate(
            credit=Sum('credit'), debit=Sum('debit'), opening_balance=Sum('opening_balance'),
            closing_balance=Sum('closing_balance'))
        # value = []
        for gl3, gl4 in zip(gl3_dss_amount, gl4_dss_amount):
            # othergl_openbal = gl3["opening_balance"] - gl4["opening_balance"]
            othergl_closebal = gl3["closing_balance"]+ gl4["closing_balance"]
            # othergl_credit = gl3["credit"] - gl4["credit"]
            # othergl_debit = gl3["debit"] - gl4["debit"]
            date = str(gl3["date__date"])
        ppr_response = ppr_source_response()
        # ppr_response.set_opening_balance(othergl_openbal)
        if othergl_closebal != 0.00:
            ppr_response.set_month_balance(othergl_closebal*-1)
        else:
            ppr_response.set_month_balance(othergl_closebal)
        # ppr_response.set_credit(othergl_credit)
        # ppr_response.set_debit(othergl_debit)
        ppr_response.set_date(str(date))
        value.append(ppr_response)
        data1 = {"name": "profitorloss", "value": value}
        value = []
        pro_list3.append(data1)
        # if pro_list2.data != None:
        #     pro_list.data+=pro_list2.data
        # if pro_list3.data != None:
        #     pro_list.data+=pro_list3.data
        return pro_list3