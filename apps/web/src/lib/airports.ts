/**
 * Geographic reference for the hub chart: where each airport is. The API gives
 * IATA codes only, so the chart looks the position up here. A code that is not
 * listed is simply left off the chart (and reported as "not plotted").
 * Coordinates are [longitude, latitude] in degrees.
 */
export type Airport = { name: string; zh: string; at: [number, number] };

export const HUB = "HKG";

export const airports: Record<string, Airport> = {
  HKG: { name: "Hong Kong", zh: "香港", at: [113.918, 22.308] },
  // East Asia
  PEK: { name: "Beijing", zh: "北京", at: [116.585, 40.08] },
  PVG: { name: "Shanghai", zh: "上海", at: [121.805, 31.143] },
  CAN: { name: "Guangzhou", zh: "廣州", at: [113.299, 23.392] },
  SZX: { name: "Shenzhen", zh: "深圳", at: [113.811, 22.639] },
  CTU: { name: "Chengdu", zh: "成都", at: [103.947, 30.578] },
  CGO: { name: "Zhengzhou", zh: "鄭州", at: [113.841, 34.52] },
  TPE: { name: "Taipei", zh: "台北", at: [121.233, 25.078] },
  ICN: { name: "Seoul", zh: "首爾", at: [126.451, 37.46] },
  NRT: { name: "Tokyo Narita", zh: "東京成田", at: [140.386, 35.765] },
  HND: { name: "Tokyo Haneda", zh: "東京羽田", at: [139.78, 35.552] },
  KIX: { name: "Osaka", zh: "大阪", at: [135.244, 34.427] },
  // South-east and South Asia
  SIN: { name: "Singapore", zh: "新加坡", at: [103.994, 1.364] },
  KUL: { name: "Kuala Lumpur", zh: "吉隆坡", at: [101.71, 2.746] },
  BKK: { name: "Bangkok", zh: "曼谷", at: [100.747, 13.69] },
  SGN: { name: "Ho Chi Minh City", zh: "胡志明市", at: [106.652, 10.819] },
  HAN: { name: "Hanoi", zh: "河內", at: [105.807, 21.221] },
  MNL: { name: "Manila", zh: "馬尼拉", at: [121.019, 14.509] },
  CGK: { name: "Jakarta", zh: "雅加達", at: [106.656, -6.126] },
  DEL: { name: "Delhi", zh: "德里", at: [77.103, 28.566] },
  BOM: { name: "Mumbai", zh: "孟買", at: [72.868, 19.089] },
  BLR: { name: "Bengaluru", zh: "班加羅爾", at: [77.706, 13.198] },
  MAA: { name: "Chennai", zh: "清奈", at: [80.169, 12.994] },
  DAC: { name: "Dhaka", zh: "達卡", at: [90.398, 23.843] },
  CMB: { name: "Colombo", zh: "可倫坡", at: [79.884, 7.181] },
  // Middle East and Africa
  DXB: { name: "Dubai", zh: "杜拜", at: [55.364, 25.253] },
  DWC: { name: "Dubai World Central", zh: "杜拜世界中心", at: [55.161, 24.896] },
  DOH: { name: "Doha", zh: "多哈", at: [51.608, 25.273] },
  AUH: { name: "Abu Dhabi", zh: "阿布達比", at: [54.651, 24.433] },
  RUH: { name: "Riyadh", zh: "利雅德", at: [46.699, 24.958] },
  TLV: { name: "Tel Aviv", zh: "特拉維夫", at: [34.886, 32.011] },
  IST: { name: "Istanbul", zh: "伊斯坦堡", at: [28.752, 41.275] },
  JNB: { name: "Johannesburg", zh: "約翰尼斯堡", at: [28.246, -26.139] },
  NBO: { name: "Nairobi", zh: "奈洛比", at: [36.928, -1.319] },
  // Europe
  LHR: { name: "London Heathrow", zh: "倫敦希斯洛", at: [-0.462, 51.47] },
  MAN: { name: "Manchester", zh: "曼徹斯特", at: [-2.275, 53.354] },
  FRA: { name: "Frankfurt", zh: "法蘭克福", at: [8.571, 50.033] },
  AMS: { name: "Amsterdam", zh: "阿姆斯特丹", at: [4.764, 52.309] },
  CDG: { name: "Paris", zh: "巴黎", at: [2.548, 49.01] },
  LGG: { name: "Liège", zh: "列日", at: [5.443, 50.637] },
  BRU: { name: "Brussels", zh: "布魯塞爾", at: [4.484, 50.901] },
  LUX: { name: "Luxembourg", zh: "盧森堡", at: [6.211, 49.627] },
  LEJ: { name: "Leipzig", zh: "萊比錫", at: [12.242, 51.424] },
  MXP: { name: "Milan", zh: "米蘭", at: [8.728, 45.63] },
  MAD: { name: "Madrid", zh: "馬德里", at: [-3.567, 40.472] },
  ZRH: { name: "Zurich", zh: "蘇黎世", at: [8.549, 47.458] },
  // Oceania
  SYD: { name: "Sydney", zh: "悉尼", at: [151.177, -33.946] },
  MEL: { name: "Melbourne", zh: "墨爾本", at: [144.843, -37.673] },
  BNE: { name: "Brisbane", zh: "布里斯本", at: [153.117, -27.384] },
  PER: { name: "Perth", zh: "珀斯", at: [115.967, -31.94] },
  AKL: { name: "Auckland", zh: "奧克蘭", at: [174.792, -37.008] },
  // Americas
  ANC: { name: "Anchorage", zh: "安克拉治", at: [-149.996, 61.174] },
  YVR: { name: "Vancouver", zh: "溫哥華", at: [-123.184, 49.195] },
  SEA: { name: "Seattle", zh: "西雅圖", at: [-122.309, 47.449] },
  SFO: { name: "San Francisco", zh: "三藩市", at: [-122.375, 37.619] },
  LAX: { name: "Los Angeles", zh: "洛杉磯", at: [-118.408, 33.943] },
  HNL: { name: "Honolulu", zh: "檀香山", at: [-157.922, 21.319] },
  DFW: { name: "Dallas", zh: "達拉斯", at: [-97.038, 32.897] },
  ORD: { name: "Chicago", zh: "芝加哥", at: [-87.905, 41.979] },
  CVG: { name: "Cincinnati", zh: "辛辛那提", at: [-84.668, 39.049] },
  MEM: { name: "Memphis", zh: "孟菲斯", at: [-89.977, 35.042] },
  SDF: { name: "Louisville", zh: "路易維爾", at: [-85.736, 38.174] },
  ATL: { name: "Atlanta", zh: "亞特蘭大", at: [-84.428, 33.637] },
  MIA: { name: "Miami", zh: "邁阿密", at: [-80.291, 25.793] },
  JFK: { name: "New York", zh: "紐約", at: [-73.779, 40.64] },
  YYZ: { name: "Toronto", zh: "多倫多", at: [-79.631, 43.677] },
  MEX: { name: "Mexico City", zh: "墨西哥城", at: [-99.072, 19.436] },
};
