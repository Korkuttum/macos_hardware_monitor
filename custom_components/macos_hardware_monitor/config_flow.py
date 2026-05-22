import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN, DEFAULT_NAME, CONF_API_URL, DEFAULT_SCAN_INTERVAL

# Konfigürasyon formu için şema (API URL + Scan Interval)
DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_URL, description={"suggested_value": "http://"}): str,
    vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
})

# Options formu için şema (SADECE scan interval)
OPTIONS_SCHEMA = vol.Schema({
    vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
})

class MacOSHWConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """macOS Hardware Monitor için yapılandırma akışı"""
    
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Kullanıcıdan API URL'sini ve scan interval'i al"""
        errors = {}
        
        if user_input is not None:
            api_url = user_input.get(CONF_API_URL, "").strip()
            scan_interval = user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            
            # URL validasyonu
            if not api_url.startswith(("http://", "https://")):
                errors["base"] = "invalid_url"
            elif not api_url.endswith("/api"):
                errors["base"] = "invalid_api_endpoint"
            else:
                # URL geçerli, API'yi test et
                if await self._test_api_connection(api_url):
                    return self.async_create_entry(
                        title=f"macOS Hardware Monitor ({api_url})",
                        data={
                            CONF_API_URL: api_url,
                            "scan_interval": scan_interval
                        }
                    )
                else:
                    errors["base"] = "cannot_connect"
        
        # Form gösterimi için açıklama metni
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "example_url": "http://192.168.1.87:8080/api",
                "default_interval": DEFAULT_SCAN_INTERVAL,
            }
        )
    
    async def _test_api_connection(self, url):
        """API bağlantısını test et"""
        import aiohttp
        import async_timeout
        
        try:
            async with async_timeout.timeout(5):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            # API'nin doğru formatta veri döndürdüğünü kontrol et
                            if isinstance(data, list) and len(data) > 0:
                                return True
                        return False
        except Exception:
            return False
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options flow'u döndür (sadece scan interval için)"""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """macOS Hardware Monitor için options akışı - SADECE scan interval"""
    
    def __init__(self, config_entry):
        self.config_entry = config_entry
    
    async def async_step_init(self, user_input=None):
        """Options formunu göster - sadece scan interval"""
        if user_input is not None:
            # Sadece scan_interval'i güncelle
            return self.async_create_entry(
                title="",
                data={
                    "scan_interval": user_input["scan_interval"]
                }
            )
        
        # Mevcut scan interval değerini göster
        current_interval = self.config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("scan_interval", default=current_interval): cv.positive_int,
            }),
            description_placeholders={
                "current_interval": current_interval,
                "default_interval": DEFAULT_SCAN_INTERVAL,
                "note": "Not: API URL'sini değiştirmek için entegrasyonu silip tekrar ekleyin."
            }
        )
