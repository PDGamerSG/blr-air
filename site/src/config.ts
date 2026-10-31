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

// Online submissions for Stranger Builds close on Sunday 8 November (India time).
export const SUBMISSIONS_CLOSE = new Date("2026-11-08T23:59:59+05:30");

export interface Locality {
  name: string;
  lat: number;
  lon: number;
}

// Mirrors blr_air/localities.py: approximate neighbourhood centroids, not sensor locations.
export const LOCALITIES: Locality[] = [
  { name: "HSR Layout", lat: 12.9116, lon: 77.6389 },
  { name: "Koramangala", lat: 12.9352, lon: 77.6245 },
  { name: "Indiranagar", lat: 12.9784, lon: 77.6408 },
  { name: "Whitefield", lat: 12.9698, lon: 77.75 },
  { name: "Electronic City", lat: 12.8452, lon: 77.6602 },
  { name: "Jayanagar", lat: 12.925, lon: 77.5938 },
  { name: "JP Nagar", lat: 12.9063, lon: 77.5857 },
  { name: "BTM Layout", lat: 12.9166, lon: 77.6101 },
  { name: "Bellandur", lat: 12.9304, lon: 77.6784 },
  { name: "Marathahalli", lat: 12.9591, lon: 77.6974 },
  { name: "Sarjapur", lat: 12.86, lon: 77.786 },
  { name: "Yelahanka", lat: 13.1005, lon: 77.5963 },
  { name: "Hebbal", lat: 13.0354, lon: 77.5988 },
  { name: "Malleshwaram", lat: 13.0031, lon: 77.5643 },
  { name: "Rajajinagar", lat: 12.9915, lon: 77.553 },
  { name: "Banashankari", lat: 12.9255, lon: 77.5468 },
  { name: "Basavanagudi", lat: 12.9422, lon: 77.5738 },
  { name: "Cubbon Park", lat: 12.9763, lon: 77.5929 },
  { name: "Lalbagh", lat: 12.9507, lon: 77.5848 },
  { name: "Bengaluru", lat: 12.9716, lon: 77.5946 },
];

export const PROMPTS = [
  { text: "best 1-hour window to run in HSR Layout", tag: "RUN" },
  { text: "best 2-hour cycling window in Koramangala tomorrow morning", tag: "CYCLE" },
  { text: "when is the air cleanest in Whitefield", tag: "CURIOUS" },
  { text: "can I take kids outside in Jayanagar tomorrow morning", tag: "KIDS" },
  { text: "best time to commute in Electronic City today", tag: "COMMUTE" },
  { text: "walk in Indiranagar tomorrow evening", tag: "WALK" },
  { text: "best 2-hour walk in Melbourne, Australia", tag: "GLOBAL" },
  { text: "best time to run in New York, US tomorrow morning", tag: "GLOBAL" },
  { text: "best window to walk in Paris, France today", tag: "GLOBAL" },
  { text: "best 2-hour cycling window in Hebbal this evening", tag: "CYCLE" },
];
