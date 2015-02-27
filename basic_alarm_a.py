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
import time
import json
from cbcommslib import CbApp
from cbconfig import *

# Default values:
config = {
    "sensors": [],
    "cid": "none",
    "client_test": "False"
}
ENFILE     = CB_CONFIG_DIR + "basic_alarm.state"
CONFIGfILE = CB_CONFIG_DIR + "basic_alarm.config"

class Client():
    def __init__(self, aid):
        self.aid = aid
        self.count = 0
        self.messages = []

    def send(self, data):
        message = {
                   "source": self.aid,
                   "destination": config["cid"],
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

class EnableState():
    def __init__(self):
        pass
        
    def isEnabled(self):
        try:
            with open(ENFILE, 'r') as f:
                self.val = int(f.read())
            if self.val == 1:
                return True
            else:
                return False
        except Exception as ex:
            self.cbLog("warning", "Could not read enable state from file")
            self.cbLog("warning", "Exception: " + str(type(ex)) + str(ex.args))
            return False

    def enable(self, en):
        if en:
            val = 1
        else:
            val = 0
        try:
            with open(ENFILE, 'w') as f:
                f.write(str(val))
        except Exception as ex:
            self.cbLog("warning", "Could not write enable state to file")
            self.cbLog("warning", "Exception: " + str(type(ex)) + str(ex.args))

class App(CbApp):
    def __init__(self, argv):
        self.appClass = "control"
        self.state = "stopped"
        self.sensorsID = [] 
        self.onSensors = []
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

    def setNames(self):
        if config["sensors"] == []:
            for d in self.idToName:
                config["sensors"].append(d)
        else:
            for n in config["sensors"]:
                found = False
                for d in self.idToName:
                    self.cbLog("debug", "setName. Matching n: " + n + " with d: " + d + " , idToName[d]: " + self.idToName[d])
                    if n == self.idToName[d]:
                        loc = config["sensors"].index(n) 
                        config["sensors"][loc] = d
                        found = True
                        break
                if not found:
                    self.cbLog("info", "setNames. Sensor name does not exist: " + n)
        self.cbLog("debug", "setNames. sensors: " + str(config["sensors"]))

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
        #self.cbLog("debug", "onAdaptorData. message: " + str(message))
        if message["id"] in self.sensorsID:
            if message["characteristic"] == "buttons":
                if message["data"]["rightButton"] == 1:
                    self.enableState.enable(True)
                elif message["data"]["leftButton"] == 1:
                    self.enableState.enable(False)
                self.cbLog("debug", "onAdaptorData. alarm: " + str(self.enableState.isEnabled()))
            elif message["characteristic"] == "number_buttons":
                for m in message["data"].keys():
                    if m == "1":
                        self.enableState.enable(True)
                    elif m == "3":
                        self.enableState.enable(False)
                self.cbLog("debug", "onAdaptorData. alarm: " + str(self.enableState.isEnabled()))
            elif message["characteristic"] == "binary_sensor":
                if self.enableState.isEnabled() and message["data"] == "on":
                    if not message["id"] in self.onSensors:
                        self.onSensors.append(message["id"])
                        msg = {"m": "intruder",
                               "t": time.time(),
                               "s": self.idToName[message["id"]]
                          }
                        self.client.send(msg)
                else:
                    if message["id"] in self.onSensors:
                        self.onSensors.remove(message["id"])
                self.cbLog("debug", "onSensors: " + str(self.onSensors))

    def onConfigureMessage(self, managerConfig):
        global config
        try:
            with open(CONFIGfILE, 'r') as f:
                newConfig = json.load(f)
                self.cbLog("debug", "Read sch_app.config")
                config.update(newConfig)
        except Exception as ex:
            self.cbLog("warning", "basic_alarm.config does not exist or file is corrupt")
            self.cbLog("warning", "Exception: " + str(type(ex)) + str(ex.args))
        for c in config:
            if c.lower in ("true", "t", "1"):
                config[c] = True
            elif c.lower in ("false", "f", "0"):
                config[c] = False
        self.cbLog("debug", "Config: " + str(config))
        if config["cid"] == "none":
            self.cbLog("warning", "No Client ID (CID) specified. App will not report intruders.")
        self.client = Client(self.id)
        self.client.sendMessage = self.sendMessage
        self.client.cbLog = self.cbLog
        for adaptor in managerConfig["adaptors"]:
            adtID = adaptor["id"]
            if adtID not in self.devices:
                # Because managerConfigure may be re-called if devices are added
                name = adaptor["name"]
                friendly_name = adaptor["friendly_name"]
                self.cbLog("debug", "managerConfigure app. Adaptor id: " +  adtID + " name: " + name + " friendly_name: " + friendly_name)
                self.idToName[adtID] = friendly_name.replace(" ", "_")
                self.devices.append(adtID)
        self.setNames()
        self.enableState = EnableState() 
        self.enableState.cbLog = self.cbLog
        self.setState("starting")

if __name__ == '__main__':
    app = App(sys.argv)
