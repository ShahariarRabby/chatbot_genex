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

FB_URL = "https://graph.facebook.com/v3.3/me/messages?access_token="
CRM_API = "http://genex-crm.herokuapp.com/crm/v1/get"
app.secret_key = "keepitsecret"

@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=2)

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
    data = json.dumps(data)
    response = requests.post(query_string,params=params,headers=headers,data = data,auth=("apikey",password))
    if response.status_code == 200:
        s = response.json()
        try:
            print(s["intents"][0]["intent"])
            intent = s["intents"][0]["intent"]
            text = s["output"]["text"][0]
            return intent,text
        except:
            return None,"Sorry! I didn't Undestand."
    else:
        return "!!SLAP!!"

@app.route("/",methods=["GET","POST"])
def index():
    if request.method=="GET":
        return render_template("index.html")

@app.route('/temp', methods=['POST'])
def temp():
    message = request.form['mes']
    # START

    # intents = ['callertuneserviceinfo', 'CallerTuneStatus', 'CallerTuneUpdate', 'discountOffer',
    # 'InternetPackageStatus', 'InternetPackageUpdate', 'MissedCallStatus', 'MissedCallUpdate']
    intents = {'callertuneserviceinfo':"call_tune_service_status", 'CallerTuneStatus':"call_tune_service_status", 'CallerTuneUpdate':"call_tune_service_status", 'discountOffer':"discount_offer",
    'InternetPackageStatus':"internet_package_status", 'InternetPackageUpdate':"internet_package_status", 'MissedCallStatus':"missed_call_status", 'MissedCallUpdate':"missed_call_status"}
    ph = re.search("\d{11}",message)
    tok = re.search("\d{4}",message)

    if ph and len(message)==11:
        print(type(ph.string))
        ph = ph.string
        crm_output = requests.post(CRM_API,data = json.dumps({"phone":ph}))
        crm_output = ast.literal_eval(crm_output.content.decode('utf-8'))

        if crm_output["found"] == "true":
            session["phone_number"] = ph
            if send_code(ph):
                return "A 4-digit token has sent to your registered number. Please enter the token as it is."
            else:
                return "Unable to send OTP."
        else:
            return "I could not find your number in our system. please enter the valid phone number."

    elif tok and len(message)==4:
        tok = tok.string
        if "phone_number" in session:
            if verify(session["phone_number"],tok):
                session["verify"] = True
                return "Thank you for verifying your identity."
            else:
                return "your OTP is not correct"

    else:
        int,output = get_bot_response(message)
        if int not in intents.keys():
            return output
        else:
            if "verify" in session:

                # END
                print(session)
                payload = {"phone":session["phone_number"]}
                row = requests.post(CRM_API,data=json.dumps(payload))
                crm_output = ast.literal_eval(row.content.decode('utf-8'))
                response = crm_output[intents[int]]
                if row.status_code == 200:
                    return str(response)
                else:
                    return "Something bad happened! :("
            else:
                return "you are not verified. Please Enter your 11 digit phone number to verify."

if __name__=="__main__":
    app.run()
