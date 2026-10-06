// Bundled Antarctic navigation configuration datasets
import type { PortInfo, ResearchCenterInfo, VesselInfo, SimulationConfig, IcebergsListResponse } from "../types";

export const FALLBACK_PORTS: PortInfo[] = [
  {
    "port_id": "hobart_au",
    "name": "Hobart",
    "country": "Australia",
    "latitude": -42.8826,
    "longitude": 147.3257,
    "description": "Major Antarctic departure port in Tasmania, Australia. Home to the Australian Antarctic Division.",
    "facilities": [
      "fuel",
      "provisions",
      "ice_breaker_support",
      "scientific_equipment"
    ],
    "timezone": "Australia/Hobart"
  },
  {
    "port_id": "christchurch_nz",
    "name": "Christchurch",
    "country": "New Zealand",
    "latitude": -43.5321,
    "longitude": 172.6362,
    "description": "Gateway to Antarctica via Lyttelton Port. Closest major port to the Ross Sea sector.",
    "facilities": [
      "fuel",
      "provisions",
      "cargo_handling"
    ],
    "timezone": "Pacific/Auckland"
  },
  {
    "port_id": "bluff_nz",
    "name": "Bluff",
    "country": "New Zealand",
    "latitude": -46.6,
    "longitude": 168.35,
    "description": "Southernmost port in New Zealand. Used for Antarctic resupply operations.",
    "facilities": [
      "fuel",
      "provisions",
      "cargo_handling"
    ],
    "timezone": "Pacific/Auckland"
  },
  {
    "port_id": "cape_town_za",
    "name": "Cape Town",
    "country": "South Africa",
    "latitude": -33.9249,
    "longitude": 18.4241,
    "description": "Primary departure port for the Indian Ocean sector of Antarctica. Home to SANAP program.",
    "facilities": [
      "fuel",
      "provisions",
      "ice_breaker_support",
      "scientific_equipment",
      "dry_dock"
    ],
    "timezone": "Africa/Johannesburg"
  },
  {
    "port_id": "ushuaia_ar",
    "name": "Ushuaia",
    "country": "Argentina",
    "latitude": -54.8019,
    "longitude": -68.303,
    "description": "Most popular departure port for Antarctic expeditions. Gateway to the Antarctic Peninsula.",
    "facilities": [
      "fuel",
      "provisions",
      "cargo_handling"
    ],
    "timezone": "America/Argentina/Ushuaia"
  },
  {
    "port_id": "punta_arenas_cl",
    "name": "Punta Arenas",
    "country": "Chile",
    "latitude": -53.1638,
    "longitude": -70.9171,
    "description": "Chilean port used for Antarctic operations. Gateway to the Antarctic Peninsula sector.",
    "facilities": [
      "fuel",
      "provisions",
      "ice_breaker_support",
      "cargo_handling"
    ],
    "timezone": "America/Santiago"
  }
];

export const FALLBACK_RESEARCH_CENTERS: ResearchCenterInfo[] = [
  {
    "center_id": "mcmurdo_us",
    "name": "McMurdo Station",
    "latitude": -77.8469,
    "longitude": 166.6687,
    "country": "United States",
    "description": "Largest Antarctic research station operated by the US Antarctic Program. Located on Ross Island.",
    "elevation_m": 0,
    "sector": "Ross Sea",
    "active": true
  },
  {
    "center_id": "scott_base_nz",
    "name": "Scott Base",
    "latitude": -77.8463,
    "longitude": 166.7647,
    "country": "New Zealand",
    "description": "New Zealand's Antarctic research station on Ross Island, near McMurdo Station.",
    "elevation_m": 0,
    "sector": "Ross Sea",
    "active": true
  },
  {
    "center_id": "mawson_au",
    "name": "Mawson Station",
    "latitude": -67.6025,
    "longitude": 62.8747,
    "country": "Australia",
    "description": "Australian research station in Mac. Robertson Land. One of the oldest continuously operating stations.",
    "elevation_m": 16,
    "sector": "Prydz Bay",
    "active": true
  },
  {
    "center_id": "davis_au",
    "name": "Davis Station",
    "latitude": -68.5764,
    "longitude": 77.9682,
    "country": "Australia",
    "description": "Australian research station in the Vestfold Hills, Princess Elizabeth Land.",
    "elevation_m": 12,
    "sector": "Prydz Bay",
    "active": true
  },
  {
    "center_id": "casey_au",
    "name": "Casey Station",
    "latitude": -66.2825,
    "longitude": 110.5247,
    "country": "Australia",
    "description": "Australian research station in the Windmill Islands, Budd Coast.",
    "elevation_m": 42,
    "sector": "Budd Coast",
    "active": true
  },
  {
    "center_id": "halley_uk",
    "name": "Halley VI Research Station",
    "latitude": -75.583,
    "longitude": -26.658,
    "country": "United Kingdom",
    "description": "British Antarctic Survey station on the Brunt Ice Shelf. Modular and relocatable.",
    "elevation_m": 30,
    "sector": "Brunt Ice Shelf",
    "active": true
  },
  {
    "center_id": "syowa_jp",
    "name": "Syowa Station",
    "latitude": -69.0003,
    "longitude": 39.5833,
    "country": "Japan",
    "description": "Japanese Antarctic research station on East Ongul Island, L\u00c3\u00bctzow-Holm Bay.",
    "elevation_m": 21,
    "sector": "L\u00c3\u00bctzow-Holm Bay",
    "active": true
  },
  {
    "center_id": "neumayer_de",
    "name": "Neumayer Station III",
    "latitude": -70.65,
    "longitude": -8.2667,
    "country": "Germany",
    "description": "German research station on the Ekstr\u00c3\u00b6m Ice Shelf, Atka Bay.",
    "elevation_m": 42,
    "sector": "Queen Maud Land",
    "active": true
  },
  {
    "center_id": "bharati_in",
    "name": "Bharati Station",
    "latitude": -69.3994,
    "longitude": 76.2477,
    "country": "India",
    "description": "Indian research station on the Larsemann Hills, Princesse Elizabeth Land. Operational since 2012.",
    "elevation_m": 28,
    "sector": "Prydz Bay",
    "active": true
  },
  {
    "center_id": "maitri_in",
    "name": "Maitri Station",
    "latitude": -70.7667,
    "longitude": 11.7333,
    "country": "India",
    "description": "Indian research station in Schirmacher Oasis, Queen Maud Land. Operational since 1989.",
    "elevation_m": 117,
    "sector": "Queen Maud Land",
    "active": true
  },
  {
    "center_id": "concorda_fr_it",
    "name": "Concordia Station",
    "latitude": -75.1,
    "longitude": 123.35,
    "country": "France/Italy",
    "description": "Franco-Italian station at Dome C on the Antarctic Plateau. One of the most remote stations.",
    "elevation_m": 3233,
    "sector": "Dome C",
    "active": true
  },
  {
    "center_id": "princess_elisabeth_be",
    "name": "Princess Elisabeth Station",
    "latitude": -71.95,
    "longitude": 23.35,
    "country": "Belgium",
    "description": "Zero-emission Antarctic research station in Dronning Maud Land.",
    "elevation_m": 1397,
    "sector": "Queen Maud Land",
    "active": true
  },
  {
    "center_id": "jang_bogo_kr",
    "name": "Jang Bogo Station",
    "latitude": -74.6167,
    "longitude": 164.2167,
    "country": "South Korea",
    "description": "South Korean research station near Terra Nova Bay, Ross Sea.",
    "elevation_m": 28,
    "sector": "Ross Sea",
    "active": true
  },
  {
    "center_id": "zhongshan_cn",
    "name": "Zhongshan Station",
    "latitude": -69.3733,
    "longitude": 76.375,
    "country": "China",
    "description": "Chinese research station on the Larsemann Hills, East Antarctica.",
    "elevation_m": 18,
    "sector": "Prydz Bay",
    "active": true
  },
  {
    "center_id": "villa_las_estrellas_cl",
    "name": "Villa Las Estrellas",
    "latitude": -62.1917,
    "longitude": -58.9633,
    "country": "Chile",
    "description": "Chilean civilian settlement and research station on King George Island, South Shetland Islands.",
    "elevation_m": 10,
    "sector": "South Shetland Islands",
    "active": true
  }
] as unknown as ResearchCenterInfo[];

export const FALLBACK_VESSELS: VesselInfo[] = [
  {
    "vessel_id": "polar_explorer",
    "name": "MV Ivan Papanin",
    "type": "ice_breaker",
    "length_m": 120,
    "beam_m": 22,
    "draft_m": 8.5,
    "displacement_tons": 8500,
    "max_speed_knots": 16,
    "cruise_speed_knots": 12,
    "fuel_rate_lph": 1372.5,
    "ice_class": "PC3",
    "safety_distance_nm": 10.8,
    "fuel_capacity_tons": 1200,
    "fuel_consumption_tons_per_day": {
      "cruise_speed": 28,
      "max_speed": 45,
      "slow_speed": 18
    },
    "range_nautical_miles": {
      "cruise_speed": 15000,
      "slow_speed": 20000
    },
    "description": "Heavy icebreaker rated for year-round operation in medium first-year ice.",
    "sensors": [
      "GPS",
      "radar",
      "sonar",
      "weather_station",
      "ice_radar"
    ],
    "status": "available"
  },
  {
    "vessel_id": "research_vessel_sagar",
    "name": "MV Vasiliy Golovnin",
    "type": "research_vessel",
    "length_m": 105,
    "beam_m": 18,
    "draft_m": 6.5,
    "displacement_tons": 5500,
    "max_speed_knots": 15,
    "cruise_speed_knots": 11,
    "fuel_rate_lph": 980.4,
    "ice_class": "PC5",
    "safety_distance_nm": 10.8,
    "fuel_capacity_tons": 800,
    "fuel_consumption_tons_per_day": {
      "cruise_speed": 20,
      "max_speed": 32,
      "slow_speed": 14
    },
    "range_nautical_miles": {
      "cruise_speed": 12000,
      "slow_speed": 16000
    },
    "description": "Indian research vessel used for Antarctic expeditions and oceanographic research.",
    "sensors": [
      "GPS",
      "radar",
      "sonar",
      "weather_station",
      "CTD"
    ],
    "status": "available"
  },
  {
    "vessel_id": "supply_cargo",
    "name": "I/B Vladimir Ignatyuk",
    "type": "cargo",
    "length_m": 130,
    "beam_m": 20,
    "draft_m": 7.0,
    "displacement_tons": 7000,
    "max_speed_knots": 14,
    "cruise_speed_knots": 10,
    "fuel_rate_lph": 1470.6,
    "ice_class": "PC4",
    "safety_distance_nm": 10.8,
    "fuel_capacity_tons": 1500,
    "fuel_consumption_tons_per_day": {
      "cruise_speed": 30,
      "max_speed": 48,
      "slow_speed": 20
    },
    "range_nautical_miles": {
      "cruise_speed": 14000,
      "slow_speed": 18000
    },
    "description": "General purpose cargo vessel configured for Antarctic resupply operations.",
    "sensors": [
      "GPS",
      "radar",
      "weather_station"
    ],
    "status": "available"
  }
] as unknown as VesselInfo[];

export const FALLBACK_SIMULATION_CONFIG: SimulationConfig = {
  "description": "Default simulation parameters for the Antarctic Navigation DSS",
  "time_step_hours": 2,
  "real_time_multiplier": 1,
  "max_simulation_hours": 720,
  "default_vessel_id": "polar_explorer",
  "default_departure_port_id": "hobart_au",
  "default_destination_id": "mcmurdo_us",
  "default_journey_mode": "outbound",
  "navigation": {
    "grid_resolution_degrees": 0.5,
    "risk_weights": {
      "sea_ice_concentration": 0.35,
      "iceberg_proximity": 0.3,
      "weather_severity": 0.2,
      "distance_penalty": 0.15
    },
    "safety_thresholds": {
      "max_safe_sea_ice_concentration": 0.6,
      "iceberg_exclusion_radius_km": 20,
      "min_distance_from_ice_edge_km": 30,
      "max_wind_speed_knots": 50,
      "max_wave_height_m": 8
    },
    "fuel_efficiency_weight": 0.4,
    "safety_weight": 0.6,
    "route_update_interval_hours": 2
  },
  "vessel": {
    "default_speed_knots": 12,
    "min_speed_knots": 4,
    "max_speed_knots": 16,
    "turn_rate_degrees_per_minute": 2
  },
  "display": {
    "map_default_center": [
      -75,
      0
    ],
    "map_default_zoom": 3,
    "track_point_interval_hours": 2,
    "show_ice_edge": true,
    "show_icebergs": true,
    "show_route": true,
    "show_risk_zones": true
  }
};

export const FALLBACK_ICEBERGS: IcebergsListResponse = {
  "icebergs": [
    {
      "iceberg_id": "A23A",
      "latitude": -62.02,
      "longitude": -52.23,
      "length_km": 74.08,
      "width_km": 59.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A64",
      "latitude": -60.53,
      "longitude": -49.56,
      "length_km": 11.11,
      "width_km": 5.56,
      "last_observed": "2022-12-09 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A69A",
      "latitude": -60.74,
      "longitude": -49.94,
      "length_km": 12.96,
      "width_km": 9.26,
      "last_observed": "2022-12-09 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A69B",
      "latitude": -59.14,
      "longitude": -53.01,
      "length_km": 5.56,
      "width_km": 3.7,
      "last_observed": "2022-09-09 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A69C",
      "latitude": -59.8,
      "longitude": -50.7,
      "length_km": 7.41,
      "width_km": 3.7,
      "last_observed": "2022-09-16 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A70",
      "latitude": -61.68,
      "longitude": -52.34,
      "length_km": 12.96,
      "width_km": 7.41,
      "last_observed": "2023-06-24 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A74A",
      "latitude": -72.1,
      "longitude": -54.12,
      "length_km": 55.56,
      "width_km": 33.34,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A74B",
      "latitude": -67.49,
      "longitude": -55.22,
      "length_km": 14.82,
      "width_km": 7.41,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A76A",
      "latitude": -55.45,
      "longitude": -34.41,
      "length_km": 57.41,
      "width_km": 7.41,
      "last_observed": "2023-06-24 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A76B",
      "latitude": -65.12,
      "longitude": -56.43,
      "length_km": 37.04,
      "width_km": 12.96,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A76C",
      "latitude": -65.21,
      "longitude": -57.35,
      "length_km": 29.63,
      "width_km": 12.96,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A76F",
      "latitude": -55.14,
      "longitude": -34.34,
      "length_km": 88.9,
      "width_km": 9.26,
      "last_observed": "2023-07-07 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A76H",
      "latitude": -55.64,
      "longitude": -34.82,
      "length_km": 51.86,
      "width_km": 5.56,
      "last_observed": "2023-07-07 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A76L",
      "latitude": -55.81,
      "longitude": -34.1,
      "length_km": 31.48,
      "width_km": 3.7,
      "last_observed": "2023-07-07 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A76M",
      "latitude": -55.63,
      "longitude": -34.38,
      "length_km": 64.82,
      "width_km": 7.41,
      "last_observed": "2023-06-24 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A77",
      "latitude": -72.34,
      "longitude": -55.55,
      "length_km": 50.0,
      "width_km": 7.41,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A78",
      "latitude": -60.47,
      "longitude": -31.32,
      "length_km": 33.34,
      "width_km": 7.41,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A79",
      "latitude": -71.09,
      "longitude": -60.49,
      "length_km": 17.59,
      "width_km": 5.56,
      "last_observed": "2022-05-06 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A80A",
      "latitude": -65.29,
      "longitude": -57.05,
      "length_km": 20.37,
      "width_km": 16.67,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A80B",
      "latitude": -71.43,
      "longitude": -60.33,
      "length_km": 24.08,
      "width_km": 9.26,
      "last_observed": "2022-12-02 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A80C",
      "latitude": -71.61,
      "longitude": -60.56,
      "length_km": 14.82,
      "width_km": 3.7,
      "last_observed": "2022-12-09 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A80D",
      "latitude": -64.93,
      "longitude": -56.03,
      "length_km": 11.11,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "A82",
      "latitude": -72.94,
      "longitude": -72.38,
      "length_km": 22.22,
      "width_km": 11.11,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B09B",
      "latitude": -66.17,
      "longitude": 143.43,
      "length_km": 50.0,
      "width_km": 18.52,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B09G",
      "latitude": -68.19,
      "longitude": 41.71,
      "length_km": 22.22,
      "width_km": 12.96,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B09I",
      "latitude": -56.19,
      "longitude": -22.68,
      "length_km": 12.96,
      "width_km": 5.56,
      "last_observed": "2022-06-24 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B15AB",
      "latitude": -72.19,
      "longitude": -15.9,
      "length_km": 20.37,
      "width_km": 7.41,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B22A",
      "latitude": -71.41,
      "longitude": -115.24,
      "length_km": 81.49,
      "width_km": 44.45,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B28",
      "latitude": -74.05,
      "longitude": -110.12,
      "length_km": 14.82,
      "width_km": 9.26,
      "last_observed": "2022-12-09 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B29",
      "latitude": -73.74,
      "longitude": -110.5,
      "length_km": 20.37,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B39",
      "latitude": -70.74,
      "longitude": -56.37,
      "length_km": 14.82,
      "width_km": 7.41,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B40",
      "latitude": -65.2,
      "longitude": 128.49,
      "length_km": 9.26,
      "width_km": 9.26,
      "last_observed": "2022-03-25 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B42",
      "latitude": -62.78,
      "longitude": -138.05,
      "length_km": 14.82,
      "width_km": 5.56,
      "last_observed": "2022-09-23 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B45",
      "latitude": -72.17,
      "longitude": -114.33,
      "length_km": 14.82,
      "width_km": 11.11,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B46",
      "latitude": -63.73,
      "longitude": -140.88,
      "length_km": 33.34,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B47",
      "latitude": -73.9,
      "longitude": -134.12,
      "length_km": 35.19,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "B50",
      "latitude": -57.85,
      "longitude": -149.11,
      "length_km": 5.56,
      "width_km": 3.7,
      "last_observed": "2022-09-16 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C15",
      "latitude": -65.93,
      "longitude": 143.18,
      "length_km": 25.93,
      "width_km": 18.52,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C18B",
      "latitude": -65.69,
      "longitude": 81.17,
      "length_km": 37.04,
      "width_km": 7.41,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C24",
      "latitude": -64.84,
      "longitude": 96.02,
      "length_km": 20.37,
      "width_km": 5.56,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C29",
      "latitude": -66.06,
      "longitude": 142.75,
      "length_km": 12.96,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C30",
      "latitude": -64.78,
      "longitude": 96.29,
      "length_km": 16.67,
      "width_km": 5.56,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C31",
      "latitude": -64.68,
      "longitude": 96.5,
      "length_km": 16.67,
      "width_km": 5.56,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C33",
      "latitude": -65.72,
      "longitude": 122.24,
      "length_km": 20.37,
      "width_km": 7.41,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C35",
      "latitude": -66.27,
      "longitude": 142.99,
      "length_km": 14.82,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C36",
      "latitude": -67.91,
      "longitude": 147.46,
      "length_km": 42.6,
      "width_km": 29.63,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C37",
      "latitude": -64.5,
      "longitude": 100.24,
      "length_km": 14.82,
      "width_km": 5.56,
      "last_observed": "2023-02-10 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C38A",
      "latitude": -65.22,
      "longitude": 101.16,
      "length_km": 11.11,
      "width_km": 5.56,
      "last_observed": "2023-02-17 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C38B",
      "latitude": -64.86,
      "longitude": 98.59,
      "length_km": 14.82,
      "width_km": 12.96,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C39",
      "latitude": -64.65,
      "longitude": 98.31,
      "length_km": 27.78,
      "width_km": 14.82,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "C40",
      "latitude": -66.39,
      "longitude": 110.1,
      "length_km": 12.96,
      "width_km": 7.41,
      "last_observed": "2023-06-24 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D20A",
      "latitude": -62.24,
      "longitude": -47.09,
      "length_km": 25.93,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D23",
      "latitude": -69.43,
      "longitude": 74.7,
      "length_km": 12.96,
      "width_km": 11.11,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D26",
      "latitude": -69.19,
      "longitude": 29.44,
      "length_km": 29.63,
      "width_km": 3.7,
      "last_observed": "2023-05-12 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D27",
      "latitude": -71.48,
      "longitude": -47.77,
      "length_km": 14.82,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D28",
      "latitude": -55.85,
      "longitude": -35.31,
      "length_km": 55.56,
      "width_km": 35.19,
      "last_observed": "2023-11-24 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D29A",
      "latitude": -60.4,
      "longitude": -20.42,
      "length_km": 38.89,
      "width_km": 16.67,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D29B",
      "latitude": -57.39,
      "longitude": -40.68,
      "length_km": 24.08,
      "width_km": 12.96,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D29C",
      "latitude": -59.42,
      "longitude": -34.86,
      "length_km": 24.08,
      "width_km": 11.11,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D30A",
      "latitude": -55.85,
      "longitude": -40.95,
      "length_km": 72.23,
      "width_km": 20.37,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D30B",
      "latitude": -60.87,
      "longitude": -44.98,
      "length_km": 27.78,
      "width_km": 9.26,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D31",
      "latitude": -60.4,
      "longitude": -34.98,
      "length_km": 29.63,
      "width_km": 3.7,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D32",
      "latitude": -65.32,
      "longitude": 53.7,
      "length_km": 18.52,
      "width_km": 16.67,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D33A",
      "latitude": -69.6,
      "longitude": -1.94,
      "length_km": 62.97,
      "width_km": 18.52,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    },
    {
      "iceberg_id": "D33B",
      "latitude": -69.68,
      "longitude": 6.9,
      "length_km": 38.89,
      "width_km": 22.22,
      "last_observed": "2023-12-21 00:00:00+00:00",
      "source": "iceberg_processed.csv",
      "demo": false
    }
  ],
  "count": 65,
  "classification": "real_iceberg",
  "demo": false,
  "warning": null
};
