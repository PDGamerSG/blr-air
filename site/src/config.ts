// Every outbound link lives here so the page can be repointed without touching markup logic.
export const AGENT_ADDRESS = "agent1q2z89ttne7p57zq7r473lrc5jan899raacv6sjqj9eymk7kdqzkwkxhcwg3";
export const PLANNER_ADDRESS = "agent1qtehmnqextcf6czcujeq3yfh5umr2qtz4cxyxknve5tlcxgdkmpdgp4x53p";
export const AGENT_HANDLE = "@blr-air";

export const LINKS = {
  asiOne: `https://asi1.ai/ai/${AGENT_ADDRESS}`,
  agentverse: `https://agentverse.ai/agents/details/${AGENT_ADDRESS}/profile`,
  agentverseHome: "https://agentverse.ai/",
  github: "https://github.com/PDGamerSG/blr-air",
  roast: "https://github.com/PDGamerSG/blr-air/issues/new?title=Roast%3A%20&labels=feedback",
  uagentDocs: "https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation",
  strangerBuilds: "https://strangerbuilds.com/",
  strangerWorld: "https://app.strangerbuilds.com/world",
  openMeteo: "https://open-meteo.com/",
  cams: "https://atmosphere.copernicus.eu/",
} as const;

// Online submissions close Sun 8 Nov, 23:59 Argentina time, which is 02:59 UTC on Monday.
export const SUBMISSIONS_CLOSE = new Date("2026-11-09T02:59:00Z");

export interface Locality {
  name: string;
  lat: number;
  lon: number;
}

// Mirrors delhi_air/localities.py: approximate neighbourhood centroids, not sensor locations.
export const LOCALITIES: Locality[] = [
  { name: "Hauz Khas", lat: 28.5494, lon: 77.2001 },
  { name: "Connaught Place", lat: 28.6315, lon: 77.2167 },
  { name: "Chandni Chowk", lat: 28.6506, lon: 77.2303 },
  { name: "Karol Bagh", lat: 28.6514, lon: 77.1907 },
  { name: "Civil Lines", lat: 28.6796, lon: 77.2244 },
  { name: "Rohini", lat: 28.7366, lon: 77.1132 },
  { name: "Bawana", lat: 28.799, lon: 77.033 },
  { name: "Punjabi Bagh", lat: 28.6683, lon: 77.1313 },
  { name: "Janakpuri", lat: 28.6219, lon: 77.0878 },
  { name: "Dwarka", lat: 28.5921, lon: 77.046 },
  { name: "Vasant Kunj", lat: 28.52, lon: 77.159 },
  { name: "Saket", lat: 28.5245, lon: 77.2066 },
  { name: "Lodhi Garden", lat: 28.5931, lon: 77.2197 },
  { name: "India Gate", lat: 28.6129, lon: 77.2295 },
  { name: "Lajpat Nagar", lat: 28.5677, lon: 77.2433 },
  { name: "Okhla", lat: 28.5361, lon: 77.2711 },
  { name: "Mayur Vihar", lat: 28.609, lon: 77.295 },
  { name: "Anand Vihar", lat: 28.6469, lon: 77.3152 },
  { name: "Noida", lat: 28.5355, lon: 77.391 },
  { name: "Gurugram", lat: 28.4595, lon: 77.0266 },
  { name: "Ghaziabad", lat: 28.6692, lon: 77.4538 },
  { name: "Faridabad", lat: 28.4089, lon: 77.3178 },
  { name: "Delhi", lat: 28.6139, lon: 77.209 },
];

const NCR_CITIES = new Set(["Noida", "Gurugram", "Ghaziabad", "Faridabad"]);
export const localityLabel = (name: string) => `${name}, ${NCR_CITIES.has(name) ? "Delhi NCR" : "Delhi"}`;

export const PROMPTS = [
  { text: "best 1-hour window to run in Hauz Khas", tag: "RUN" },
  { text: "best 2-hour cycling window in Dwarka tomorrow morning", tag: "CYCLE" },
  { text: "when is the air cleanest in Noida", tag: "CURIOUS" },
  { text: "can I take kids outside in Saket tomorrow morning", tag: "KIDS" },
  { text: "best time to commute in Okhla today", tag: "COMMUTE" },
  { text: "walk in Lajpat Nagar tomorrow evening", tag: "WALK" },
  { text: "best 2-hour walk in Melbourne, Australia", tag: "GLOBAL" },
  { text: "best time to run in New York, US tomorrow morning", tag: "GLOBAL" },
  { text: "best window to walk in Paris, France today", tag: "GLOBAL" },
  { text: "best 2-hour cycling window in Rohini this evening", tag: "CYCLE" },
];
