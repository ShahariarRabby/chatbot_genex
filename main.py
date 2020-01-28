from flask import Flask, request, jsonify,session, render_template,redirect, url_for
# from authy.api import AuthyApiClient
from datetime import timedelta, datetime
# import pymysql
import random
import requests
import json
import ast
import re
import os
import warnings
from flask_cors import CORS
import MySQLdb

warnings.filterwarnings('ignore')

app = Flask(__name__)
cors = CORS(app, resources={r"/getintent/*": {"origins": "*"}})

def get_bot_response(message, botid):

    API_END_POINT = "http://182.160.104.220:5656/getintent?sentence="+message+"&botID="+botid

    response = requests.get(API_END_POINT)
    # print(response)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception('Something Went wrong')

def retrieve_response_from_db(botid,intent):

    try:
        db = MySQLdb.connect(host="182.160.104.220" , user="root" , passwd="iamgenex@2019A", db="Chatlogy")
        cursor = db.cursor()
    except:
        raise Exception("Cannot connect to the database")

    rows = cursor.execute("select response from responses where botid='%s' and intent='%s'" % (botid, intent))

    if rows:
        db.close()
        return cursor.fetchone()[0]
    else:
        return "No Response has been set for ->'%s'" % (intent)
    


@app.route("/",methods=["GET","POST"])
def index():
    if request.method=="GET":
        # session.clear()
        # _,_,_= get_bot_response("")
        return render_template("index.html")

@app.route("/addResp",methods=["POST"])
def addResp():
    print("I was called")
    response = request.form['response']
    botid = request.form['botid'].rstrip()
    intent = request.form['intent'].rstrip()

    try:
        db = MySQLdb.connect(host="182.160.104.220" , user="root" , passwd="iamgenex@2019A", db="Chatlogy")
        cursor = db.cursor()
    except:
        raise Exception("Cannot connect to the database")

    sql = """INSERT INTO responses(botid, intent, response) VALUES ('%s', '%s', '%s')""" % (botid, intent, response)
    
    try:
        rows = cursor.execute(sql)
        db.commit()
        db.close()

        return json.dumps(["OK"])
    except:
        db.rollback()
        db.close()
        return json.dumps(["NOT OK"])


@app.route("/addresponse",methods=["GET","POST"])
def response():
    if request.method=="GET":
        # session.clear()
        # _,_,_= get_bot_response("")
        return render_template("addResponse.html")

@app.route('/temp', methods=['POST'])
def temp():
    message = request.form['mes']
    botid = request.form['botid'].rstrip()

    response = get_bot_response(message, botid)

    if response['Status']=='success':
        if response["intent"] == 'unknown' and response["entities"].keys():
            # print(list(response["entities"].keys()))
            res = retrieve_response_from_db(botid, list(set(list(response['entities'].values())))[0])
            return json.dumps([res])

        res = retrieve_response_from_db(botid, response["intent"])

        return json.dumps([res])
    else:
        return json.dumps([response["Message"]])

if __name__=="__main__":

    # web: gunicorn main:app
    app.run(host="0.0.0.0",port=5000)
