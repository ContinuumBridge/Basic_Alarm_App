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
from cbutils import nicetime
from cbcommslib import CbApp, CbClient
from cbconfig import *
from twisted.internet import reactor

# Default values:
config = {
    "ignore_time": 120
}

ENFILE       = CB_CONFIG_DIR + "basic_alarm.state"
CONFIG_FILE  = CB_CONFIG_DIR + "basic_alarm.config"
CID          = "CID164"  # Client ID

class EnableState():
    def __init__(self):
        self.switch_ids = []
        
    def setSwitch(self, deviceID):
        if deviceID not in self.switch_ids:
            self.switch_ids.append(deviceID)

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
        for s in self.switch_ids:
            command = {"id": self.id,
                       "request": "command"}
            if en:
                command["data"] = "on"
            else:
                command["data"] = "off"
            self.sendMessage(command, s)

class App(CbApp):
    def __init__(self, argv):
        self.appClass = "control"
        self.state = "stopped"
        self.sensorsID = [] 
        self.onSensors = []
        self.devices = []
        self.idToName = {} 
        self.lastTrigger = 0
        reactor.callLater(10, self.resetSensors)
        # Super-class init must be called
        CbApp.__init__(self, argv)

    def setState(self, action):
        self.state = action
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def resetSensors(self):
        if time.time() - self.lastTrigger > config["ignore_time"]:
            self.onSensors = []
        reactor.callLater(10, self.resetSensors)

    def readLocalConfig(self):
        global config
        try:
            with open(CONFIG_FILE, 'r') as f:
                newConfig = json.load(f)
                self.cbLog("debug", "Read local config")
                config.update(newConfig)
        except Exception as ex:
            self.cbLog("warning", "Local config does not exist or file is corrupt. Exception: " + str(type(ex)) + str(ex.args))
        self.cbLog("debug", "Config: " + str(json.dumps(config, indent=4)))

    def onConcMessage(self, message):
        #self.cbLog("debug", "onConcMessage, message: " + str(json.dumps(message, indent=4)))
        if "status" in message:
            if message["status"] == "ready":
                # Do this after we have established communications with the concentrator
                msg = {
                    "m": "req_config",
                    "d": self.id
                }
                self.client.send(msg)
        self.client.receive(message)

    def onClientMessage(self, message):
        #self.cbLog("debug", "onClientMessage, message: " + str(json.dumps(message, indent=4)))
        global config
        if "config" in message:
            if "warning" in message["config"]:
                self.cbLog("warning", "onClientMessage: " + str(json.dumps(message["config"], indent=4)))
            else:
                try:
                    newConfig = message["config"]
                    copyConfig = config.copy()
                    copyConfig.update(newConfig)
                    if copyConfig != config or not os.path.isfile(CONFIG_FILE):
                        self.cbLog("debug", "onClientMessage. Updating config from client message")
                        config = copyConfig.copy()
                        with open(CONFIG_FILE, 'w') as f:
                            json.dump(config, f)
                        #self.cbLog("info", "Config updated")
                        self.readLocalConfig()
                        # With a new config, send init message to all connected adaptors
                        for i in self.adtInstances:
                            init = {
                                "id": self.id,
                                "appClass": self.appClass,
                                "request": "init"
                            }
                            self.sendMessage(init, i)
                except Exception as ex:
                    self.cbLog("warning", "onClientMessage, could not write to file. Type: " + str(type(ex)) + ", exception: " +  str(ex.args))

    def onAdaptorService(self, message):
        #self.cbLog("debug", "onAdaptorService. message: " + str(message))
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
        if switch and binary_sensor:
            binary_sensor = False  # Don't trigger on an indicator device
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
        if switch:
            self.enableState.setSwitch(message["id"])
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
                        now = time.time()
                        self.lastTrigger = now
                        self.onSensors.append(message["id"])
                        active = []
                        for a in self.onSensors:
                            active.append(self.idToName[a])
                        msg = {"m": "alert",
                               "a": "Intruder detected by " + str(", ".join(active)) + " at " + nicetime(now),
                               "t": now
                        }
                        self.client.send(msg)
                #self.cbLog("debug", "onSensors: " + str(self.onSensors))

    def onConfigureMessage(self, managerConfig):
        for adaptor in managerConfig["adaptors"]:
            adtID = adaptor["id"]
            if adtID not in self.devices:
                # Because managerConfigure may be re-called if devices are added
                name = adaptor["name"]
                friendly_name = adaptor["friendly_name"]
                #self.cbLog("debug", "managerConfigure app. Adaptor id: " +  adtID + " name: " + name + " friendly_name: " + friendly_name)
                self.idToName[adtID] = friendly_name.replace(" ", "_")
                self.devices.append(adtID)
        self.readLocalConfig()
        self.enableState = EnableState() 
        self.enableState.cbLog = self.cbLog
        self.enableState.id = self.id
        self.enableState.sendMessage = self.sendMessage
        self.client = CbClient(self.id, CID, 5)
        self.client.onClientMessage = self.onClientMessage
        self.client.sendMessage = self.sendMessage
        self.client.cbLog = self.cbLog
        self.client.loadSaved()
        self.setState("starting")

if __name__ == '__main__':
    app = App(sys.argv)
