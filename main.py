from flask import Flask, request, jsonify,session, render_template,redirect, url_for
from authy.api import AuthyApiClient
from datetime import timedelta, datetime
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
CRM_API = "http://genexcrm.eu-gb.mybluemix.net/crm/v1/get"
app.secret_key = "keepitsecret"

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
    if response.status_code == 200:
        s = response.json()
        prevContext = s["context"]
        session["prevContext"] = prevContext
        try:
            # print(s)
            intent = s["intents"][0]["intent"]
            print(s["output"]["text"])
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

    if response["actions"][0]["name"] == "triggerOTPAuthentication":
        session["requireOTP"] = True
        return json.dumps(output)
    elif response["actions"][0]["name"] == "callertune_status":
        if "isAuthenticated" in response["context"]:
            if response["context"]["isAuthenticated"]:

                payload = {"phone":session["phone_number"]}
                row = requests.post(CRM_API,data=json.dumps(payload))
                crm_output = ast.literal_eval(row.content.decode('utf-8'))

                if crm_output["call_tune_service_status"] == "1":

                    session["prevContext"][response["actions"][0]["result_variable"]] = "Activated"

                    _,out,_ = get_bot_response("hi")
                    return json.dumps(out)
                else:

                    session["prevContext"][response["actions"][0]["result_variable"]] = "Deactivated"
                    _,out,_ = get_bot_response("hi")
                    return json.dumps(out)
            else:
                session["prevContext"] = {"isAuthenticated":False}
                session["requireOTP"] = True
                _,output,_ = get_bot_response("hi")
                return json.dumps(output)

    elif response["actions"][0]["name"] == "missedcall_status":
        if "isAuthenticated" in response["context"]:
            if response["context"]["isAuthenticated"]:
                payload = {"phone":session["phone_number"]}
                row = requests.post(CRM_API,data=json.dumps(payload))
                crm_output = ast.literal_eval(row.content.decode('utf-8'))

                if crm_output["missed_call_status"] == "1":

                    session["prevContext"][response["actions"][0]["result_variable"]] = "Activated"

                    _,out,_ = get_bot_response("hi")
                    return json.dumps(out)
                else:

                    session["prevContext"][response["actions"][0]["result_variable"]] = "Deactivated"
                    _,out,_ = get_bot_response("hi")
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
        crm_output = requests.post(CRM_API,data = json.dumps({"phone":ph}))
        crm_output = ast.literal_eval(crm_output.content.decode('utf-8'))

        if crm_output["found"] == "true":
            session["phone_number"] = ph
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
            session["requireOTP"] = True

        int,output,response = get_bot_response(message)

        print(response)
        if "actions" in response.keys():
            print(int)
            print(response)
            return perform_action(output,response)
        else:
            return json.dumps(output)

if __name__=="__main__":
    app.run(debug=True)
