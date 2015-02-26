#!/usr/bin/env python
# basic_alarm_a.py
"""
Copyright (c) 2015 ContinuumBridge Limited

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys
import os.path
import time
import logging
from cbcommslib import CbApp
from cbconfig import *

class Client():
    def __init__(self, aid):
        self.aid = aid
        self.count = 0
        self.messages = []

    def send(self, data):
        message = {
                   "source": self.aid,
                   "destination": "CID71",
                   "body": data
                  }
        message["body"]["n"] = self.count
        self.count += 1
        self.messages.append(message)
        self.sendMessage(message, "conc")

    def receive(self, message):
        self.cbLog("debug", "Message from client: " + str(message))
        if "body" in message:
            if "n" in message["body"]:
                self.cbLog("debug", "Received ack from client: " + str(message["body"]["n"]))
                for m in self.messages:
                    if m["body"]["n"] == m:
                        self.messages.remove(m)
                        self.cbLog("debug", "Removed message " + str(m) + " from queue")
        else:
            self.cbLog("warning", "Received message from client with no body")

class App(CbApp):
    def __init__(self, argv):
        self.appClass = "control"
        self.state = "stopped"
        self.alarmOn = False
        self.sensorsID = [] 
        self.switchID = ""
        self.devices = []
        self.idToName = {} 
        # Super-class init must be called
        CbApp.__init__(self, argv)

    def setState(self, action):
        self.state = action
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def onAdaptorService(self, message):
        sensor = False
        switch = False
        buttons = False
        binary_sensor = False
        number_buttons = False
        for p in message["service"]:
            if p["characteristic"] == "buttons":
                buttons = True
            if p["characteristic"] == "number_buttons":
                number_buttons = True
            if p["characteristic"] == "switch":
                switch = True
            if p["characteristic"] == "binary_sensor":
                binary_sensor = True
        if buttons:
            self.sensorsID.append(message["id"])
            req = {"id": self.id,
                   "request": "service",
                   "service": [
                                 {"characteristic": "buttons",
                                  "interval": 0
                                 }
                              ]
                  }
            self.sendMessage(req, message["id"])
        if number_buttons:
            self.sensorsID.append(message["id"])
            req = {"id": self.id,
                   "request": "service",
                   "service": [
                                 {"characteristic": "number_buttons",
                                  "interval": 0
                                 }
                              ]
                  }
            self.sendMessage(req, message["id"])
        if binary_sensor:
            self.sensorsID.append(message["id"])
            req = {"id": self.id,
                   "request": "service",
                   "service": [
                                 {"characteristic": "binary_sensor",
                                  "interval": 0
                                 }
                              ]
                  }
            self.sendMessage(req, message["id"])
        self.setState("running")

    def onAdaptorData(self, message):
        self.cbLog("debug", "onAdaptorData. message: " + str(message))
        if message["id"] in self.sensorsID:
            if message["characteristic"] == "buttons":
                if message["data"]["rightButton"] == 1:
                    self.alarmOn = True
                elif message["data"]["leftButton"] == 1:
                    self.alarmOn = False
            elif message["characteristic"] == "number_buttons":
                for m in message["data"].keys():
                    if m == "1":
                        self.alarmOn = True
                    elif m == "3":
                        self.alarmOn = False
            elif message["characteristic"] == "binary_sensor":
                if self.alarmOn and message["data"] == "on":
                    msg = {"m": "intruder",
                           "t": time.time(),
                           "s": self.idToName[message["id"]]
                          }
                    self.client.send(msg)

    def onConfigureMessage(self, managerConfig):
        #logging.debug("%s onConfigureMessage, config: %s", ModuleName, config)
        self.client = Client(self.id)
        for adaptor in managerConfig["adaptors"]:
            adtID = adaptor["id"]
            if adtID not in self.devices:
                # Because managerConfigure may be re-called if devices are added
                name = adaptor["name"]
                friendly_name = adaptor["friendly_name"]
                self.cbLog("debug", "managerConfigure app. Adaptor id: " +  adtID + " name: " + name + " friendly_name: " + friendly_name)
                self.idToName[adtID] = friendly_name.replace(" ", "_")
                self.devices.append(adtID)
        self.client.sendMessage = self.sendMessage
        self.client.cbLog = self.cbLog
        self.setState("starting")

if __name__ == '__main__':
    app = App(sys.argv)
