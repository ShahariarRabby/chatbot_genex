from flask import Flask, request, jsonify,session, render_template,redirect, url_for
from authy.api import AuthyApiClient
from datetime import timedelta, datetime
import pymysql
import random
import requests
import json
import ast
import re
import os

app = Flask(__name__)

app.config.from_object('config')
api = AuthyApiClient(app.config['AUTHY_API_KEY'])
password = "uVVBM9ut54gZaWQYbs6nRZekii4S2vdPrQIAmZKgPqK0"

# FB_URL = "https://graph.facebook.com/v3.3/me/messages?access_token="
CRM_API = "https://updatedcrm.herokuapp.com/api.php?appKey=JY6WdJpkDsSgn8eC4GsS"
app.secret_key = "keepitsecret"

# sudo lsof -t -i :5000 | xargs kill -9

@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=5)

def send_code(phone_number):

    r = api.phones.verification_start(phone_number[1:],"+880","sms")

    return r.ok()

def verify(phone_number,token):
    s = api.phones.verification_check(phone_number[1:],"+880",token)

    return s.ok()

def db_connect():
    db = pymysql.connect(host=app.config["DB_HOST"],port=18785,db="CRM",user="admin",passwd=app.config["DB_PASS"])
    cur = db.cursor()
    return db,cur
def insert(db,cur,data):
    query_string = "INSERT INTO querybank (ticket, phoneNo, name, query, date) VALUES ('{}','{}','{}','{}','{}')".format(data["ticket"],data["phoneNo"],data["name"],data["query"],data["date"])
    print(query_string)
    try:
        cur.execute(query_string)
        return True
    except:
        return False

def get_bot_response(message):

    query_string = "https://gateway.watsonplatform.net/assistant/api/v1/workspaces/"+app.config['WO_ID']+"/message"
    headers = {'Content-Type':'application/json',}
    params = {'version':'2019-02-28'}
    data = {"input":{"text":""}}
    data["input"]["text"] = message
    if "prevContext" in session.keys():
        data["context"]= session["prevContext"]
    data = json.dumps(data)
    # print("payload data: "+data)
    response = requests.post(query_string,params=params,headers=headers,data = data,auth=("apikey",password))
    # print(response.json())
    if response.status_code == 200:
        s = response.json()
        prevContext = s["context"]
        session["prevContext"] = prevContext
        try:
            # print(s)
            intent = s["intents"][0]["intent"]
            # print(s["output"]["text"])/
            return intent,s["output"]["text"],s
        except:
            # print(s)
            return "Empty",s["output"]["text"],s
    else:
        return "",'["!!SLAP!!"]',""

def check_session():
    if "phone_number" in session.keys():
        return True
    else:
        return False

def perform_action(output,response):
    # print(" I am in perform_action")

    if response["actions"][0]["name"] == "triggerOTPAuthentication":
        session["requireOTP"] = True
        # print(" I am in triggerOTPAuthentication")
        return json.dumps(output)
    elif response["actions"][0]["name"] == "callertune_status":

        if "isAuthenticated" in response["context"]:
            if response["context"]["isAuthenticated"]:

                crm_api = CRM_API + "&query=user_info&phoneNo=" + session["phone_number"]
                crm_output = requests.get(crm_api)
                crm_output = crm_output.json()

                if crm_output["callerTune"] != "deactivated":

                    session["prevContext"][response["actions"][0]["result_variable"]] = "Activated"
                    _,out,_ = get_bot_response("hi")
                    out = [out[0]+" And you are using <b>"+crm_output["callerTune"]["name"]+"</b>."]
                    return json.dumps(out)
                else:

                    session["prevContext"][response["actions"][0]["result_variable"]] = "Deactivated"
                    _,out,_ = get_bot_response("hi")
                    return json.dumps(out)

    elif response["actions"][0]["name"] == "missedcall_status":
        if "isAuthenticated" in response["context"]:
            if response["context"]["isAuthenticated"]:
                crm_api = CRM_API + "&query=user_info&phoneNo=" + session["phone_number"]
                crm_output = requests.get(crm_api)
                crm_output = crm_output.json()
                if crm_output["missedCallAlert"] == "activated":
                    session["prevContext"][response["actions"][0]["result_variable"]] = "Activated"
                    # print(session["prevContext"])
                    _,out,_ = get_bot_response("hi")
                    # print(out)
                    return json.dumps(out)
                else:

                    session["prevContext"][response["actions"][0]["result_variable"]] = "Deactivated"
                    _,out,_ = get_bot_response("hi")
                    return json.dumps(out)
    elif response["actions"][0]["name"] == "internet_status":

        crm_api = CRM_API + "&query=user_info&phoneNo=" + session["phone_number"]
        crm_output = requests.get(crm_api)
        crm_output = crm_output.json()
        if crm_output["internetStatus"] != "deactivated":
            row = crm_output["internetStatus"]
            out = []
            ls = "You are using "
            ls = ls + "<b>" + row["id"] + " - " + row["packageName"] + "</b> package. <br>" + "And your current internet balance is " + row["balance"] + ".<br>" + "Valid till " + row["validity"]+"."
            out.append(ls)
            ls = ""
            return json.dumps(out)
        else:
            return json.dumps(["Currently you have no active internet package."])

    elif response["actions"][0]["name"] == "callertune_list":

        crm_api = CRM_API + "&query=caller_tune_list"
        crm_output = requests.get(crm_api)
        crm_output = crm_output.json()
        if len(crm_output)>=1:

            out = ["Here are the Caller tunes that are available right now:- <br>"]
            ls = "Code | Name<br>"
            for row in crm_output:
                ls = ls + row["id"] + " | " + row["name"] + "<br>"
            out.append(ls)
            return json.dumps(out)
        else:
            return json.dumps(["No Caller Tune is availble right now."])

    elif response["actions"][0]["name"] == "internet_list":

        crm_api = CRM_API + "&query=internet_package_list"
        crm_output = requests.get(crm_api)
        crm_output = crm_output.json()
        if len(crm_output)>=1:
            out = ["Here are the Internet Packages that are available right now:- <br>"]
            ls = ""
            for row in crm_output:
                ls = ls + "Code: " + row["id"] + "<br>" + "Name: " + row["packageName"] + "<br>" + "Quota: " + row["quota"] + "<br>" + "Validity: " + row["validity"] + " days<br>" +"Price: " + row["price"] + " Taka<br>"
                out.append(ls)
                ls = ""
            return json.dumps(out)
        else:
            return json.dumps(["No Internet Package is availble right now."])

    elif response["actions"][0]["name"] == "missedcall_activate_service":

        crm_api = CRM_API + "&query=update_missed_called_alert" + "&status=1" + "&phoneNo=" + session["phone_number"]
        crm_output = requests.post(crm_api)
        crm_output = crm_output.json()
        # print("Activating")
        if crm_output["message"] == "Updated Successfully":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Activated"
            session["prevContext"]["confirmationCheck"] = False
            _,out,_ = get_bot_response("hi")
            return json.dumps(out)
        elif crm_output["message"] == "No Changed":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Already_Active"
            session["prevContext"]["confirmationCheck"] = False
            _,out,_ = get_bot_response("hi")
            return json.dumps(out)

    elif response["actions"][0]["name"] == "missedcall_deactivate_service":

        crm_api = CRM_API + "&query=update_missed_called_alert" + "&status=0" + "&phoneNo=" + session["phone_number"]
        crm_output = requests.post(crm_api)
        crm_output = crm_output.json()
        if crm_output["message"] == "Updated Successfully":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Deactivated"
            session["prevContext"]["confirmationCheck"] = False
            _,out,_ = get_bot_response("hi")
            return json.dumps(out)
        elif crm_output["message"] == "No Changed":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Already_Deactive"
            session["prevContext"]["confirmationCheck"] = False
            _,out,_ = get_bot_response("hi")
            return json.dumps(out)

    elif response["actions"][0]["name"] == "callertune_deactivate_service":

        crm_api = CRM_API + "&query=update_caller_tune" + "&callerTuneId=0" + "&phoneNo=" + session["phone_number"]
        crm_output = requests.post(crm_api)
        crm_output = crm_output.json()
        if crm_output["message"] == "Updated Successfully":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Deactivated"
            session["prevContext"]["confirmationCheck"] = False
            # res = []
            _,out,_ = get_bot_response("hi")
            # res.append(output[0])
            # res.append(out[0])
            return json.dumps(out)
        elif crm_output["message"] == "No Changed":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Already_Deactive"
            session["prevContext"]["confirmationCheck"] = False
            _,out,_ = get_bot_response("hi")
            return json.dumps(out)

    elif response["actions"][0]["name"] == "internet_deactivate_service":

        crm_api = CRM_API + "&query=update_internet_package_status" + "&status=0" + "&phoneNo=" + session["phone_number"]
        crm_output = requests.post(crm_api)
        crm_output = crm_output.json()
        if crm_output["message"] == "Updated Successfully":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Deactivated"
            session["prevContext"]["confirmationCheck"] = False
            _,out,_ = get_bot_response("hi")
            return json.dumps(out)
        elif crm_output["message"] == "No Changed":
            session["prevContext"][response["actions"][0]["result_variable"]] = "Already_Deactive"
            session["prevContext"]["confirmationCheck"] = False
            _,out,_ = get_bot_response("hi")
            return json.dumps(out)
    elif response["actions"][0]["name"] == "rechargeHistory":

        crm_api = CRM_API + "&query=recharge_history" + "&phoneNo=" + session["phone_number"]
        crm_output = requests.post(crm_api)
        crm_output = crm_output.json()
        if len(crm_output) != 0:
            out = ["Here is your last recharge history:<br>"]
            lst = ""
            for row in crm_output:
                lst = lst + "Transaction ID: " + row["transactionID"] + "<br>Recharge Amount: " + row["amount"] + "<br>Date: " + row["rechargeDate"].split(" ")[0]
                out.append(lst)
                lst = ""
            return json.dumps(out)
        else:
            out = ["You have no recharge history"]
            return json.dumps(out)


@app.route("/",methods=["GET","POST"])
def index():
    if request.method=="GET":
        session.clear()
        _,_,_= get_bot_response("")
        return render_template("index.html")

@app.route('/temp', methods=['POST'])
def temp():
    message = request.form['mes']

    ph = re.search("\d{11}",message)
    tok = re.search("\d{4}",message)
    OTP = False
    if "requireOTP" in session.keys(): # we can use conext variable 'isAuthenticated'
        OTP = True                     # instead of this procedure
    if ph and len(message)==11 and OTP:
        session.pop("requireOTP")
        ph = ph.string
        crm_api = CRM_API + "&query=user_info&phoneNo=" + ph
        # print(crm_api)
        crm_output = requests.get(crm_api)
        crm_output = crm_output.json()

        if crm_output["phoneNo"] != None:
            session["phone_number"] = ph
            session["name"] = crm_output["name"]
            if send_code(ph):
                return '["A 4-digit token has sent to your registered number. Please enter the token as it is."]'
            else:
                return '["Unable to send OTP."]'
        else:
            return '["I could not find your number in our system. please enter the valid phone number."]'

    elif tok and len(message)==4:
        tok = tok.string
        if "phone_number" in session:
            if verify(session["phone_number"],tok):
                session["verify"] = True
                # print(session)
                if "prevContext" in session.keys():
                    session["prevContext"]["isAuthenticated"] = True
                    _,output,r = get_bot_response("hi")
                    if "actions" in r.keys():
                        return perform_action(output,r)
                    else:
                        return json.dumps(output)
                else:
                    session["prevContext"] = {"isAuthenticated":True}
                    _,output,r = get_bot_response("hi")
                    if "actions" in r.keys():
                        return perform_action(output,r)
                    else:
                        return json.dumps(output)

            else:
                # print(session)
                if "prevContext" in session.keys():
                    session["prevContext"]["isAuthenticated"] = False
                    _,output,_ = get_bot_response("hi")
                return json.dumps(output)
                # return "your OTP is not correct"
        else:
            if "prevContext" in session.keys():
                session["prevContext"]["isAuthenticated"] = False
                _,output,_ = get_bot_response("hi")
            return json.dumps(output)

    else: # for any message other than 4-digit OTP code and phone number number

        if not check_session():
            session["prevContext"] = {"isAuthenticated":False}
            # session["requireOTP"] = True

        int,output,response = get_bot_response(message)
        print(output)
        if "actions" in response.keys():
            # print(response["actions"])
            # print("hi")
            print(response["actions"])
            return perform_action(output,response)
        elif int=="General_Ending":
            session.clear()
            output = ["Thank you! It was my pleasure to serve you."]
            return json.dumps(output)
        else:
            # send the message and phone number to some portal bia API call
            # if "phone_number" in session:
            #
            #     data = {"ticket":"","phoneNo":"","name":"","query":"","date":""}
            #     data["ticket"] = "T"+str(random.randint(1000,9999))
            #     data["phoneNo"] = session["phone_number"]
            #     data["name"] = session["name"]
            #     data["query"] = message
            #     data["date"] = str(datetime.today()).split(" ")[0]
            #     db,cur = db_connect()
            #     if insert(db,cur,data):
            #         print("OK")
            #     else:
            #         print("Not OK")
            #     db.close()
            #     out = ["Sorry, currently I'm unable to assist you with this query. Should I transfer to an Human Agent for further assistance?"]
            #     return json.dumps(out)
            # else:
            #     out = ["Sorry, currently I'm unable to assist you with this query. Should I transfer to an Human Agent for further assistance?"]
            #     return json.dumps(out)
        # else:
            out = ["Sorry, currently I'm unable to assist you with this query. Should I transfer to an Human Agent for further assistance?"]
            return json.dumps(output)

if __name__=="__main__":
    app.run(debug=True)
