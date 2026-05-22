import logging
import re
import asyncio
from datetime import timedelta
import aiohttp
import async_timeout
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator, CoordinatorEntity
)
from homeassistant.helpers.entity import generate_entity_id
from .const import DOMAIN, CONF_API_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Sensörleri kur"""
    api_url = config_entry.data.get(CONF_API_URL)
    scan_interval = config_entry.data.get("scan_interval", 30)
    
    # Koordinatör: API'yi düzenli aralıklarla sorgular
    coordinator = MacOSHWCoordinator(hass, api_url, scan_interval)
    await coordinator.async_config_entry_first_refresh()
    
    # Her bir JSON öğesi için bir sensör oluştur
    sensors = []
    if coordinator.data and isinstance(coordinator.data, list):
        for item in coordinator.data:
            # Geçerli bir item mı kontrol et
            if isinstance(item, dict) and "category" in item and "description" in item:
                # Benzersiz entity ID oluştur
                raw_id = f"{item['category']}_{item['description']}"
                # Özel karakterleri temizle
                clean_id = re.sub(r'[^a-zA-Z0-9_]', '_', raw_id.lower())
                clean_id = re.sub(r'_+', '_', clean_id).strip('_')
                entity_id = generate_entity_id("sensor.{}", clean_id, hass=hass)
                
                sensors.append(MacOSSensor(coordinator, item, entity_id))
    
    if sensors:
        async_add_entities(sensors, True)
        _LOGGER.info(f"Added {len(sensors)} sensors for macOS Hardware Monitor")
    else:
        _LOGGER.warning("No sensors were created - check API response format")


class MacOSHWCoordinator(DataUpdateCoordinator):
    """API verilerini yöneten koordinatör"""
    
    def __init__(self, hass, api_url, update_interval):
        super().__init__(
            hass,
            _LOGGER,
            name="macOS Hardware Monitor",
            update_interval=timedelta(seconds=update_interval),
        )
        self.api_url = api_url

    async def _async_update_data(self):
        """API'den JSON verisini çek"""
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.api_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list):
                                _LOGGER.debug(f"Fetched {len(data)} sensors from API")
                                return data
                            else:
                                _LOGGER.error(f"API returned non-list data: {type(data)}")
                                return []
                        else:
                            _LOGGER.error(f"API error: {response.status}")
                            return []
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout fetching data from {self.api_url}")
            return []
        except Exception as e:
            _LOGGER.error(f"Error fetching data: {e}")
            return []


class MacOSSensor(CoordinatorEntity, SensorEntity):
    """Tek bir sensör entity'si"""
    
    def __init__(self, coordinator, item, entity_id):
        super().__init__(coordinator)
        self._item = item
        self._attr_unique_id = entity_id
        self.entity_id = entity_id
        self._attr_name = f"{item['category']} {item['description']}"
        
        # İkonu kategoriye göre ayarla
        self._attr_icon = self._get_icon_for_category(item.get('category', ''))
        
        _LOGGER.debug(f"Created sensor: {self._attr_name}")
    
    def _get_icon_for_category(self, category):
        """Kategoriye göre uygun Material Design ikonu döndür"""
        if not category:
            return "mdi:chip"
            
        category_lower = category.lower()
        
        # CPU, GPU, Memory gibi özel durumlar
        if "cpu" in category_lower:
            return "mdi:cpu-64-bit"
        elif "gpu" in category_lower:
            return "mdi:gpu"
        elif "memory" in category_lower or "ram" in category_lower:
            return "mdi:memory"
        elif "drive" in category_lower or "ssd" in category_lower or "hdd" in category_lower:
            return "mdi:harddisk"
        elif "network" in category_lower or "wlan" in category_lower or "airport" in category_lower:
            return "mdi:wifi"
        
        # Ana kategoriler
        if category_lower == "battery":
            return "mdi:battery"
        elif category_lower == "current":
            return "mdi:current-ac"
        elif category_lower == "fans":
            return "mdi:fan"
        elif category_lower == "power":
            return "mdi:flash"
        elif category_lower == "temperature":
            return "mdi:thermometer"
        elif category_lower == "voltage":
            return "mdi:flash-triangle"
        else:
            return "mdi:chip"
    
    def _determine_unit(self, value, category, unit_field):
        """Birimi belirle"""
        # Önce unit alanını kontrol et
        if unit_field and isinstance(unit_field, str):
            unit_lower = unit_field.lower().strip()
            if unit_lower in ["a", "amp", "ampere"]:
                return "A"
            elif unit_lower in ["v", "volt"]:
                return "V"
            elif unit_lower in ["w", "watt"]:
                return "W"
            elif unit_lower in ["°c", "c", "celsius"]:
                return "°C"
            elif unit_lower in ["rpm"]:
                return "rpm"
            elif unit_lower in ["%", "percent"]:
                return "%"
        
        # value içinden birim çıkar
        if isinstance(value, str):
            if "a" in value.lower() and "v" not in value.lower():
                return "A"
            elif "v" in value.lower():
                return "V"
            elif "w" in value.lower():
                return "W"
            elif "°c" in value.lower() or "c" in value.lower():
                return "°C"
            elif "rpm" in value.lower():
                return "rpm"
            elif "%" in value:
                return "%"
        
        # Kategoriye göre varsayılan birim
        if category == "Current":
            return "A"
        elif category == "Voltage":
            return "V"
        elif category == "Power":
            return "W"
        elif category == "Temperature":
            return "°C"
        elif category == "Fans":
            return "rpm"
        
        return None
    
    def _extract_numeric_value(self, value):
        """String'den sayısal değer çıkar"""
        if isinstance(value, (int, float)):
            return value
        
        if isinstance(value, str):
            # Sayıyı bul (ondalıklı veya tam sayı)
            match = re.search(r"(\d+(?:\.\d+)?)", value)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return value
            return value
        
        return value
    
    @property
    def native_value(self):
        """Sensörün değeri"""
        raw_value = self._item.get("value", None)
        if raw_value is None:
            return None
        
        # Sayısal değeri çıkar
        return self._extract_numeric_value(raw_value)
    
    @property
    def native_unit_of_measurement(self):
        """Birim"""
        raw_value = self._item.get("value", "")
        unit_field = self._item.get("unit", "")
        category = self._item.get("category", "")
        
        return self._determine_unit(raw_value, category, unit_field)
    
    @property
    def extra_state_attributes(self):
        """Ek öznitelikler"""
        return {
            "category": self._item.get("category"),
            "description": self._item.get("description"),
            "raw_value": self._item.get("value", ""),
            "original_unit": self._item.get("unit", ""),
            "friendly_name": f"{self._item.get('category')} {self._item.get('description')}",
        }
    
    @property
    def device_info(self):
        """Cihaz bilgisi"""
        return {
            "identifiers": {(DOMAIN, self.coordinator.api_url)},
            "name": "macOS Hardware Monitor",
            "manufacturer": "Apple",
            "model": "Mac Hardware Sensors",
            "sw_version": "1.0.0",
        }
    
    async def async_added_to_hass(self):
        """Entity hazır olduğunda"""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
    
    def _handle_coordinator_update(self):
        """Koordinatör güncellendiğinde veriyi yenile"""
        if not self.coordinator.data:
            return
            
        # Bu sensöre ait öğeyi bul
        for item in self.coordinator.data:
            if (isinstance(item, dict) and 
                item.get("category") == self._item.get("category") and 
                item.get("description") == self._item.get("description")):
                self._item = item
                self._attr_icon = self._get_icon_for_category(item.get("category", ""))
                break
        self.async_write_ha_state()