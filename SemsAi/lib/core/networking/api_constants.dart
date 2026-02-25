class ApiConstants {
  ApiConstants._();

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://youssif12-semsai-backend.hf.space',
  );

  static const String agentsUrl = String.fromEnvironment(
    'API_AGENTS_URL',
    defaultValue: 'https://youssif12-semsai-agents.hf.space',
  );

  static const String tileUrl =
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png';
  static const String userAgent = 'com.semsai.app';
  static const String mapAttribution = 'Leaflet | © OSM';
}
