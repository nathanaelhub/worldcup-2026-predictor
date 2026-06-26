/* Nation -> flag emoji, keyed to the team names used in the dataset
   (martj42/international_results). ISO2 codes are converted to regional-indicator
   emoji; UK home nations and a few specials are hard-mapped. Names not present
   here return "" — the match lab filters those out so every row shows a flag. */

const ISO2 = {
  // 2026 World Cup field
  "Algeria": "DZ", "Argentina": "AR", "Australia": "AU", "Austria": "AT",
  "Belgium": "BE", "Bosnia and Herzegovina": "BA", "Brazil": "BR", "Canada": "CA",
  "Cape Verde": "CV", "Colombia": "CO", "Croatia": "HR", "Curaçao": "CW",
  "Czech Republic": "CZ", "DR Congo": "CD", "Ecuador": "EC", "Egypt": "EG",
  "France": "FR", "Germany": "DE", "Ghana": "GH", "Haiti": "HT", "Iran": "IR",
  "Iraq": "IQ", "Ivory Coast": "CI", "Japan": "JP", "Jordan": "JO", "Mexico": "MX",
  "Morocco": "MA", "Netherlands": "NL", "New Zealand": "NZ", "Norway": "NO",
  "Panama": "PA", "Paraguay": "PY", "Portugal": "PT", "Qatar": "QA",
  "Saudi Arabia": "SA", "Senegal": "SN", "South Africa": "ZA", "South Korea": "KR",
  "Spain": "ES", "Sweden": "SE", "Switzerland": "CH", "Tunisia": "TN",
  "Turkey": "TR", "United States": "US", "Uruguay": "UY", "Uzbekistan": "UZ",
  // other rated nations
  "Italy": "IT", "Denmark": "DK", "Nigeria": "NG", "Chile": "CL", "Serbia": "RS",
  "Poland": "PL", "Greece": "GR", "Hungary": "HU", "Ukraine": "UA", "Russia": "RU",
  "Romania": "RO", "Peru": "PE", "Venezuela": "VE", "Bolivia": "BO",
  "Republic of Ireland": "IE", "Slovenia": "SI", "Slovakia": "SK", "Cameroon": "CM",
  "Mali": "ML", "Burkina Faso": "BF", "Costa Rica": "CR", "Honduras": "HN",
  "Jamaica": "JM", "Israel": "IL", "Georgia": "GE", "North Macedonia": "MK",
  "Albania": "AL", "Iceland": "IS", "Finland": "FI", "Guatemala": "GT",
  "Belarus": "BY", "Angola": "AO", "Palestine": "PS", "Guinea": "GN", "Syria": "SY",
  "Oman": "OM", "Libya": "LY", "United Arab Emirates": "AE", "China PR": "CN",
  "China": "CN", "India": "IN", "Thailand": "TH", "Vietnam": "VN", "Indonesia": "ID",
  "Malaysia": "MY", "Philippines": "PH", "Bahrain": "BH", "Kuwait": "KW",
  "Lebanon": "LB", "Kazakhstan": "KZ", "Azerbaijan": "AZ", "Armenia": "AM",
  "Luxembourg": "LU", "Cyprus": "CY", "Estonia": "EE", "Latvia": "LV",
  "Lithuania": "LT", "Montenegro": "ME", "Bulgaria": "BG",
  "Trinidad and Tobago": "TT", "Zambia": "ZM", "Kenya": "KE", "Uganda": "UG",
  "Tanzania": "TZ", "Zimbabwe": "ZW", "Gabon": "GA", "Benin": "BJ",
  "Madagascar": "MG", "Mozambique": "MZ", "Namibia": "NA", "Sudan": "SD",
  "Mauritania": "MR", "Guinea-Bissau": "GW", "Equatorial Guinea": "GQ", "Togo": "TG",
  "Niger": "NE", "Malawi": "MW", "Comoros": "KM", "Gambia": "GM", "Sierra Leone": "SL",
  "Liberia": "LR", "Botswana": "BW", "Rwanda": "RW", "Ethiopia": "ET",
  "Eswatini": "SZ", "Lesotho": "LS", "Burundi": "BI", "South Sudan": "SS",
  "Central African Republic": "CF", "Chad": "TD", "Congo": "CG", "Djibouti": "DJ",
  "Somalia": "SO", "Seychelles": "SC", "Mauritius": "MU", "Eritrea": "ER",
  "Suriname": "SR", "Guyana": "GY", "Nicaragua": "NI", "El Salvador": "SV",
  "Belize": "BZ", "Cuba": "CU", "Dominican Republic": "DO", "Grenada": "GD",
  "Barbados": "BB", "Bermuda": "BM", "Antigua and Barbuda": "AG", "Aruba": "AW",
  "Puerto Rico": "PR", "Guam": "GU", "Fiji": "FJ", "Papua New Guinea": "PG",
  "Solomon Islands": "SB", "Vanuatu": "VU", "Tahiti": "PF", "Samoa": "WS",
  "Tonga": "TO", "Cook Islands": "CK", "Nepal": "NP", "Bangladesh": "BD",
  "Sri Lanka": "LK", "Pakistan": "PK", "Afghanistan": "AF", "Maldives": "MV",
  "Bhutan": "BT", "Myanmar": "MM", "Cambodia": "KH", "Laos": "LA", "Mongolia": "MN",
  "Brunei": "BN", "Singapore": "SG", "Hong Kong": "HK", "Chinese Taipei": "TW",
  "Macau": "MO", "Tajikistan": "TJ", "Turkmenistan": "TM", "Kyrgyzstan": "KG",
  "Kyrgyz Republic": "KG", "Yemen": "YE", "Moldova": "MD", "Malta": "MT",
  "Gibraltar": "GI", "Faroe Islands": "FO", "Andorra": "AD", "San Marino": "SM",
  "Liechtenstein": "LI", "North Korea": "KP", "Korea DPR": "KP",
  "Saint Lucia": "LC", "St Lucia": "LC", "Saint Kitts and Nevis": "KN",
  "St Kitts and Nevis": "KN", "Saint Vincent and the Grenadines": "VC",
  "New Caledonia": "NC", "Réunion": "RE",
  // common aliases that may appear in the source data
  "Cabo Verde": "CV", "Czechia": "CZ", "Türkiye": "TR", "Côte d'Ivoire": "CI",
  "Korea Republic": "KR", "USA": "US",
};

const SPECIAL = {
  "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
  "Northern Ireland": "🇬🇧", "Kosovo": "🇽🇰",
};

function flagOf(name) {
  if (SPECIAL[name]) return SPECIAL[name];
  const iso = ISO2[name];
  if (!iso) return "";
  return String.fromCodePoint(...[...iso].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

const hasFlag = (name) => !!(SPECIAL[name] || ISO2[name]);

window.WCFlags = { flagOf, hasFlag };
