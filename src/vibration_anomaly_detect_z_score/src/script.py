"""Script reading Acceleration data from MQTT, calculates anomalys and send it to InfluxDB"""
import logging
import paho.mqtt.client as mqtt
import os
import json
import statistics
import math
import influxdb_client
from influxdb_client.client.write_api import WriteOptions
from datetime import datetime


# Set loging system
LOG_FORMAT = "%(levelname)s %(asctime)s \
    Function: %(funcName)s \
    Line: %(lineno)d \
    Message: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
LOGGER = logging.getLogger(__name__)

# Geting parameters from env variable
def get_para(
    env: str, req_type=None, default: str | int | float = None
) -> str | int | float:
    """Function read env variable and return require value of it with log information

    Args:
        env (str): Name of enviromental variable
        req_type (str, int, float): define which type shoud have returned env variable.
        default (str, int, float): will be returnet if is set and env variable does not exist

    Raises:
        SystemExit: Stop program if set type_var has not passed validate
        SystemExit: Stop program if env does not exist and default is not set
        SystemExit: Stop program if cannot convert env variable to req_type
    """
    # set local variable. Type and value of readed env variable
    env_type = type(env)
    env_val = os.getenv(env, None)

    # check if input convert type is correct or is None (if not, return error and stop program)
    allow_convert = [str, int, float]
    if req_type not in allow_convert and req_type != None:
        LOGGER.error(
            f"Cannot convert value of env {env} to {req_type}. Allowed convert type: str, int, float"
        )
        raise SystemExit

    # Return value of env variable
    if env_val == None and default == None:
        # env does not exist and we did not set default value
        LOGGER.error(f"Env variable {env} does not exist")
        raise SystemExit
    elif env_val == None:
        # env does not exist but return default (default is different than none)
        LOGGER.warning(
            f"Env variable {env} does not exist, return default value: {default}"
        )
        return default
    elif env_type != req_type and req_type != None:
        # env var exist and it's type is diffrent than what we set
        try:
            converted_env = req_type(env_val)
            LOGGER.info(
                f"Env variable {env} value: {env_val}. Converted from {env_type} to {req_type}."
            )
            return converted_env
        except Exception as e:
            LOGGER.error(
                f"Convert env variable {env} from {env_type} to {req_type} failed: {e}"
            )
            raise SystemExit
    else:
        # env exist, is the same type (or we not set type) so we return it
        LOGGER.info(f"Env variable {env} value: {env_val}, type: {env_type}")
        return env_val



# Assignment const variable from env or created using env
LOGGER.info("Seting const global variables")

LINE_NAME = get_para("LINE_NAME", str)
MACHINE_NAME = get_para("MACHINE_NAME", str)
SENSOR_NAME = get_para("SENSOR_NAME", str)

MQTT_USERNAME = get_para("MQTT_USERNAME", str)
MQTT_PASSWORD = get_para("MQTT_PASSWORD", str)
MQTT_HOST = get_para("MQTT_HOST", str)
MQTT_PORT = get_para("MQTT_PORT", int)
MQTT_QOS = get_para("MQTT_QOS", int)
MQTT_TOPIC = LINE_NAME + "/" + MACHINE_NAME + "/" + SENSOR_NAME
LOGGER.info(f"MQTT_TOPIC value is: {MQTT_TOPIC} ")

INFLUX_HOST = get_para("INFLUX_HOST", str)
INFLUX_PORT = get_para("INFLUX_PORT", str)
INFLUX_PROCESS_DB = get_para("INFLUX_PROCESS_DB", str)
INFLUX_BATCH_SIZE = get_para("INFLUX_BATCH_SIZE", int)
INFLUX_FLUSH_INTERVAL = get_para("INFLUX_FLUSH_INTERVAL", int)
INFLUX_JITTER_INTERVAL = get_para("INFLUX_JITTER_INTERVAL", int)
INFLUX_ORG = get_para("INFLUX_ORG", str)
INFLUX_TOKEN = get_para("INFLUX_TOKEN", str)
INFLUX_URL = "http://" + INFLUX_HOST + ":" + INFLUX_PORT
LOGGER.info(f"INFLUX_URL value is:  {INFLUX_URL} ")

#Threshold for z-score value. Point above this threshold is treated as anomaly 
Z_SCORE_THRESHOLD = get_para("Z_SCORE_THRESHOLD", float, default=2.0) 

#Number of model points in list to calculate anomaly
MODEL_WINDOW_SIZE = get_para("MODEL_WINDOW_SIZE", int, default=100)

#Number of anomaly point in list to calculate anomaly ration
ANOMALY_LIST_SIZE = get_para("ANOMALY_LIST_SIZE", int, default=100)

# Algorithm for anomaly detection with +-3 sigma method 
class AnomalyDetectionZscore:
    """Class of anomaly detection object."""

    # Init function
    def __init__(self, model_window_size: int, model_name: str, logger) -> None:
        self._model_points = []
        self._anomaly_list = []
        self._anomaly = 0
        self._model_avg = 0.0
        self._model_std = 0.0
        self._z_score = 0.0
        self._anomaly_ratio = 0.0
        self._u_thresh = 0.0
        self._l_thresh = 0.0
        self._model_window_size = model_window_size
        self._model_name = model_name
        self._logger = logger

    # Read only wariables
    @property
    def anomaly(self):
        return self._anomaly

    @property
    def model_avg(self):
        return self._model_avg

    @property
    def model_std(self):
        return self._model_std

    @property
    def anomaly_ratio(self):
        return self._anomaly_ratio

    # Check proces of creation model is complete
    def is_model_complete(self) -> bool:
        """Return bool information wheter model has enought point in list"""
        return True if len(self._model_points) == self._model_window_size else False

    # Calculate anomaly ratio -> sum all anomalies (0 and 1) in anomaly_list to get total number of all ones (1)
    def do_anomaly_ratio(self, anomaly_list_size: int):
        """Calculate anomaly ratio. Create list of anomaly results (0 and 1), sum them and divide by size of that list

        Args:
            anomaly_list_size (int): size of anomaly list to calculate ratio
        """
        try:
            if self.is_model_complete() == False:
                pass
            elif len(self._anomaly_list) < anomaly_list_size:
                self._anomaly_list.append(self._anomaly)
            else:
                self._anomaly_list.pop(0)
                self._anomaly_list.append(self._anomaly)
                self._anomaly_ratio = sum(self._anomaly_list) / anomaly_list_size
        except Exception as e:
            self._logger.error(
                f"Calculation anomaly ratio of model {self._model_name} failed. Error code/reason: {e}"
            )

    # Build model and calculate if new point is anomaly or not
    def check_if_anomaly(self, value, limit: int = 0):
        """3sigma alghoritm to check if argument value is anomaly or not.

        Args:
            value (any): input value to evaluate by algorithm

            limit (int): limit to avoid get to small u_thresh and l_thresh. Example: if your value is a time,
            and std will be lower than possible time value (min time will be probe frequency),
            all next points will be anomaly.
        """

        try:
            if self.is_model_complete() == False:
                # building first model
                self._model_points.append(value)
            else:
                self._model_avg = abs(statistics.mean(self._model_points))
                self._model_std = abs(statistics.stdev(self._model_points))
                self._z_score = (abs(value) - self._model_avg) / self._model_std 

                # Check if new point is above z-score threshold i.e. this is anomaly
                if abs(self._z_score) > Z_SCORE_THRESHOLD:
                    self._anomaly = 1
                else:
                    self._model_points.pop(0)
                    self._model_points.append(value)
                    self._anomaly = 0
                

        except Exception as e:
            self._logger.error(
                f'Calculation anomaly of model "{self._model_name}" failed. Error code/reason: {e}'
            )


# Function trigered when connect to MQTT Broker
def on_connect(mqttclient, userdata, flags, rc, properties):
    """Method triggered by mqtt on connect callback and log information about status of connection

    Args:
        mqttclient: the client instance for this callback
        userdata:  the private user data as set in Client() or userdata_set()
        flags: response flags sent by the broker
        rc: the connection result code
    """
    if rc == 0:
        LOGGER.info("Connection to MQTT Broker sucesfull. Result Code: 0")
    elif rc == 1:
        LOGGER.warning(
            "Connection to MQTT Broker refused - incorrect protocol version. Result Code: 1}"
        )
    elif rc == 2:
        LOGGER.warning(
            "Connection to MQTT Broker refused - invalid client identifier. Result Code: 2"
        )
    elif rc == 3:
        LOGGER.warning(
            "Connection to MQTT Broker refused – server unavailable. Result Code: 3"
        )
    elif rc == 4:
        LOGGER.warning(
            "Connection to MQTT Broker refused – bad username or password. Result Code: 4"
        )
    elif rc == 5:
        LOGGER.warning(
            "Connection to MQTT Broker refused – not authorised. Result Code: 5"
        )
    else:
        LOGGER.warning(f"Conection problem (unknown result code). Result Code: {rc}")


# Function trigered when unexpect disconnect from MQTT Broker
def on_disconnect(mqttclient, userdata, rc, properties):
    """Method triggered by mqtt on disconnect callback and log information about lost connection

    Args:
        mqttclient: the client instance for this callback
        userdata:  the private user data as set in Client() or userdata_set()
        rc: the connection result code
    """
    LOGGER.info(f"Lost conection with MQTT Broker. Result Code: {rc}")


# Function trigered when message come to MQTT Broker
def on_message(mqttclient, userdata, message):
    """Method triggered when data apear on mqtt topic. Method is responisble for:
        1. Read acceleration data from mqtt broker
        2. Detect anomalys of total rms
        2. Send data to InfluxDB

    Args:
        mqttclient: the client instance for this callback
        userdata:  the private user data as set in Client() or userdata_set()
        message: data from MQTT topic
    """
    # Prepare recived mqtt data
    data = message.payload.decode("utf-8")
    #data = data.replace("\u0000", "")
    mqtt_data = json.loads(data)

    # Calculating total rms
    total_rms = round(
        float(
            math.sqrt(
                mqtt_data["VibAccelTotal_RMS_X"] ** 2
                + mqtt_data["VibAccelTotal_RMS_Y"] ** 2
                + mqtt_data["VibAccelTotal_RMS_Z"] ** 2
            )
        ),
        5,
    )

    # Anomaly detection of vib sensor
    vib_sensor.check_if_anomaly(total_rms)
    vib_sensor.do_anomaly_ratio(ANOMALY_LIST_SIZE)

    # Send data to InfluxDB
    try:
        measurement = ("VibSensor")
        
        point = (
            influxdb_client.Point(measurement)
            .tag("line_name", str(mqtt_data["LineName"]))
            .tag("machine_name", str(mqtt_data["MachineName"]))
            .tag("sensor_name", str(mqtt_data["SensorName"]))
            .field("vib_accel_rms_x", round(float(mqtt_data["VibAccelTotal_RMS_X"]), 4))
            .field("vib_accel_rms_y", round(float(mqtt_data["VibAccelTotal_RMS_Y"]), 4))
            .field("vib_accel_rms_z", round(float(mqtt_data["VibAccelTotal_RMS_Z"]), 4))
            .field("vib_accel_rms_total", round(float(total_rms), 4))
            #.field("contactTemperature", round(float(mqtt_data["Contact_Temp"]), 2))
            .field("anomaly", int(vib_sensor.anomaly))
            .field("avg_window", round(float(vib_sensor.model_avg), 4))
            .field("std_window", round(float(vib_sensor.model_std), 4))
            .field("anomaly_ratio", round(float(vib_sensor.anomaly_ratio), 4))
            .time(
                time=datetime.utcfromtimestamp(int(mqtt_data["TimeStamp"]) / 1000),
                write_precision="ms",
            )
        )
        
        with influx_client.write_api(write_options=write_options) as write_api:
             write_api.write(INFLUX_PROCESS_DB, INFLUX_ORG, point)
        
    except Exception as e:
        LOGGER.error(f"Send data to InfluxDB failed. Error code/reason: {e}")


# Main function of script
if __name__ == "__main__":

    # Creating vibration sensor anomaly object
    vib_sensor = AnomalyDetectionZscore(MODEL_WINDOW_SIZE, "Acceleration", LOGGER)

    # Configuring conection with InfluxDB database
    try:
        LOGGER.info("Configuring InfluxDB client ")
        influx_client = influxdb_client.InfluxDBClient(
            url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, enable_gzip=False
        )

        LOGGER.info("Configuring InfluxDB write api")
        write_options = WriteOptions(batch_size=INFLUX_BATCH_SIZE, 
                                     flush_interval=INFLUX_FLUSH_INTERVAL, 
                                     jitter_interval=INFLUX_JITTER_INTERVAL, 
                                     retry_interval=1000)

    except Exception as e:
        LOGGER.error(f"Configuring InfluxDB failed. Error code/reason: {e}")

    # Configuring MQTT connection and subscribe topic
    try:
        LOGGER.info("Configuring MQTT")
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        mqtt_client.connect(MQTT_HOST, MQTT_PORT)
        mqtt_client.subscribe(MQTT_TOPIC, MQTT_QOS)
    except Exception as e:
        LOGGER.error(f"Configuring MQTT failed. Error code/reason: {e}")

    mqtt_client.loop_forever()

