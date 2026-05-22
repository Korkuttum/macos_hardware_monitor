import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN, DEFAULT_NAME, CONF_API_URL, DEFAULT_SCAN_INTERVAL

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_URL): str,
    vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
})

class MacOSHWConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # URL validasyonu
            if user_input[CONF_API_URL].startswith(("http://", "https://")):
                return self.async_create_entry(
                    title=DEFAULT_NAME, data=user_input
                )
            else:
                errors["base"] = "invalid_url"
        
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "url_example": "http://192.168.1.87:8080/api"
            }
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        schema = vol.Schema({
            vol.Required(
                CONF_API_URL,
                default=self.config_entry.data.get(CONF_API_URL)
            ): str,
            vol.Optional(
                "scan_interval", 
                default=self.config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ): cv.positive_int,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
