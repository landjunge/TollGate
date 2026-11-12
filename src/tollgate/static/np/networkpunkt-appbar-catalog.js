/* Original assets, explicitly assigned for FIVE-TOOL-DESIGN-20261107. */
export const CATALOG_VERSION = "1.2.1";
export const APP_CATALOG = Object.freeze([
  {
    "id": "kirabridge",
    "name": {
      "de": "KiraBridge",
      "en": "KiraBridge"
    },
    "icon": "np-appbar-kirabridge-dark-256.png",
    "color": "#fc63ad",
    "art": [
      14,
      26,
      214,
      204
    ],
    "colorSource": "kirabridge:assets/design/icons/dark/KiraBridge-dark-256.png#original-frame-color",
    "routes": [
      "host-adapter"
    ]
  },
  {
    "id": "threaddesk",
    "name": {
      "de": "ThreadDesk",
      "en": "ThreadDesk"
    },
    "icon": "np-appbar-threaddesk-dark-256.png",
    "color": "#b99cff",
    "art": [
      35,
      40,
      186,
      176
    ],
    "colorSource": "threaddesk:brand/README.md",
    "routes": [
      "host-adapter"
    ]
  },
  {
    "id": "4allpass",
    "name": {
      "de": "4AllPass",
      "en": "4AllPass"
    },
    "icon": "np-appbar-4allpass-dark-256.png",
    "color": "#6be4f2",
    "art": [
      33,
      38,
      190,
      180
    ],
    "colorSource": "4allpass:brand/ap4/dark/4allpass-dark-256.png#original-frame-color",
    "routes": [
      "host-adapter"
    ]
  },
  {
    "id": "tollgate",
    "name": {
      "de": "TollGate",
      "en": "TollGate"
    },
    "icon": "np-appbar-tollgate-dark-256.png",
    "color": "#e77745",
    "art": [
      35,
      40,
      186,
      176
    ],
    "colorSource": "tollgate:brand/README.md",
    "routes": [
      "host-adapter"
    ]
  },
  {
    "id": "agent-authority",
    "name": {
      "de": "Agent Authority",
      "en": "Agent Authority"
    },
    "icon": "np-appbar-agent-authority-dark-256.png",
    "color": "#3b78fc",
    "art": [
      14,
      23,
      219,
      211
    ],
    "colorSource": "agent-authority:assets/design/icons/dark/Agent-Authority-dark-256.png#original-frame-color",
    "routes": [
      "host-adapter"
    ]
  }
].map(entry => Object.freeze({...entry, name:Object.freeze(entry.name), art:Object.freeze(entry.art), routes:Object.freeze(entry.routes)})));
export const ASSET_BLOCKERS = Object.freeze({});
export const COLOR_BLOCKERS = Object.freeze({});
