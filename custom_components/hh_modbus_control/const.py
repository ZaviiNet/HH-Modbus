DOMAIN = "hh_modbus_control"
CONTROLLER = "modbus_controller"
SLAVE = "modbus_controller_slave"

VALUES = "values"
VALUE = "value"
REGISTER = "register"
SENSOR_ENTITIES = "sensor_entities"
TIME_ENTITIES = "time_entities"
SWITCH_ENTITIES = "switch_entities"
NUMBER_ENTITIES = "number_entities"
SENSOR_DERIVED_ENTITIES = "sensor_derived_entities"
DRIFT_COUNTER = "drift_counter"
ENTITIES = "entities"

# Inverter brands
INVERTER_BRAND = "inverter_brand"
BRAND_SOLIS = "solis"
BRAND_SUNSYNK = "sunsynk"
BRAND_LABELS = {BRAND_SOLIS: "Solis", BRAND_SUNSYNK: "Sun-Synk / Deye"}

MANUFACTURER_SOLIS = "Solis"
MANUFACTURER_SUNSYNK = "Sun-Synk"

# Connection types
CONN_TYPE_TCP = "tcp"
CONN_TYPE_SERIAL = "serial"

# Serial connection parameters
CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_CONNECTION_TYPE = "connection_type"
CONF_INVERTER_SERIAL = "inverter_serial"
CONF_SLAVE = "slave"

# Default serial values
DEFAULT_BAUDRATE = 9600
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
